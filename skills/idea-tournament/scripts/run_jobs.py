#!/usr/bin/env python3
"""Run idea-tournament jobs on Claude (headless `claude -p`) or any OpenRouter model, with no sub-agents.

Every job is a brief file. The runner pastes in every existing file the brief names by absolute path (inputs),
asks the model for the content of every path that does not exist yet (outputs), writes those files, checks the
format, retries once, and logs exact tokens and cost. Jobs whose outputs all exist are skipped, so re-running is safe.

Usage:
  run_jobs.py --model z-ai/glm-5.3-flash JOB [JOB ...]       # JOB = brief path, or path:letter for packed-score.md
  run_jobs.py --model claude:sonnet JOB [JOB ...]            # Claude through `claude -p` (your Claude Code login)
  run_jobs.py --model ... --court <trials-dir> <slug> [...]   # run whole trials: advance, run, repeat until done
Options: --concurrency 8  --max-tokens 16000  --log usage.jsonl  --dry-run
OpenRouter key: $OPENROUTER_API_KEY, else the first line of ~/.config/openrouter/key. Never printed or logged.
Claude jobs run `claude -p` with no tools, settings, MCP servers or session file: one model call per job, and the
exact cost Claude Code reports is logged (on a subscription that cost counts against usage limits instead of a bill).
"""
import concurrent.futures as cf, json, os, re, ssl, subprocess, sys, tempfile, time, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blind import strip_card

API = "https://openrouter.ai/api/v1/chat/completions"
HERE = os.path.dirname(os.path.abspath(__file__))
# Absolute file paths only: at least two directories deep and ending in a file extension (so "/wk" or "/60" never match).
PATH_RE = re.compile(r"(/(?:[^/\s`'\"()<>,;]+/){2,}[^/\s`'\"()<>,;]+\.[A-Za-z0-9]+)")
SYSTEM = ("You complete exactly one job for an idea-evaluation tournament. The job brief is given first, followed by "
          "the full contents of every file it refers to, so you never need to open anything. Follow the brief exactly "
          "(role, rules, word limits, format). Use only facts in the brief and the included files.")


def tls_context():
    """Verified TLS everywhere. python.org's macOS Python ships without CA certs, so fall back to certifi or the
    system bundle instead of ever disabling verification."""
    ctx = ssl.create_default_context()
    if ctx.get_ca_certs():
        return ctx
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for f in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/opt/homebrew/etc/openssl@3/cert.pem"):
        if os.path.exists(f):
            return ssl.create_default_context(cafile=f)
    return ctx


TLS = tls_context()


def api_key(model):
    if model.startswith("claude:"):
        return None
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not k:
        p = os.path.expanduser("~/.config/openrouter/key")
        if os.path.exists(p):
            k = open(p).readline().strip()
    if not k:
        sys.exit("No OpenRouter key. In your own terminal (not a chat), run:\n  python3 "
                 + os.path.join(HERE, "openrouter_key.py"))
    return k


def plan(job):
    path, _, letter = job.partition(":") if not os.path.exists(job) else (job, "", "")
    brief = open(path).read()
    if letter:
        brief = brief.replace("<letter>", letter)
    seen, inputs, outputs = set(), [], []
    for m in PATH_RE.finditer(brief):
        p = m.group(1)
        if p in seen or p == os.path.abspath(path):
            continue
        seen.add(p)
        if os.path.isfile(p):
            inputs.append(p)
        elif not os.path.isdir(p) and os.path.isdir(os.path.dirname(p)):
            outputs.append(p)
    return path, brief, inputs, outputs


def build_messages(brief, inputs, outputs):
    parts = ["# Job brief\n\n" + brief]
    for p in inputs:
        parts.append(f"# File: {p}\n\n" + open(p).read())
    if len(outputs) == 1:
        how = (f"Your whole reply is written verbatim to {outputs[0]}. Reply with only that file's content: "
               "no preamble, no code fences.")
    else:
        how = ("Reply with ONE JSON object and nothing else: {\"files\": {\"<path>\": \"<full file content>\", ...}} "
               "with exactly these paths: " + ", ".join(outputs))
    parts.append("# How to answer\n\n" + how)
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


def strip_fences(t):
    t = t.strip()
    m = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", t, re.S)
    return m.group(1).strip() if m else t


CARD_CAP = 450


def check(path, content, ids=()):
    if path.endswith(".json"):
        data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        # Blind scoring replies must score every idea in the round, in every section, or the medians go wrong.
        for section in ("rubric", "judges"):
            if ids and isinstance(data.get(section), dict):
                missing = sorted(set(ids) - set(data[section]))
                if missing:
                    raise ValueError(f"'{section}' is missing ideas {missing}: score every idea")
        if "pick" in data and data["pick"] not in (1, 2):
            raise ValueError("'pick' must be 1 or 2")
    if "/jury/" in path and not re.search(r"^VOTE:\s*(NOT GUILTY|GUILTY)", content, re.M):
        raise ValueError("juror file needs a 'VOTE: GUILTY' or 'VOTE: NOT GUILTY' line")
    if path.endswith(".card.md"):
        if not content.lstrip().startswith("Build \""):
            raise ValueError('card must start with: Build "<Name>"')
        words = len(strip_card(content, "Idea XXX").split())  # counted exactly as blind.py counts it
        if words > CARD_CAP:
            raise ValueError(f"{os.path.basename(path)} is {words} words; the cap is {CARD_CAP}. Rewrite it to about "
                             f"{int(CARD_CAP * 0.8)} words: cut repetition and asides, keep every mechanism")


def call(model, messages, max_tokens, key):
    if model.startswith("claude:"):
        return call_claude(model.split(":", 1)[1], messages)
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens,
                       "usage": {"include": True}}).encode()
    for attempt in range(5):
        req = urllib.request.Request(API, body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                                 "X-Title": "idea-tournament"})
        try:
            with urllib.request.urlopen(req, timeout=300, context=TLS) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
        except urllib.error.URLError:
            if attempt < 4:
                time.sleep(2 ** attempt * 3)
                continue
            raise


def call_claude(model, messages):
    """One headless Claude Code call with no tools; returns the same shape as an OpenRouter response."""
    system = messages[0]["content"]
    convo = messages[1:]
    prompt = convo[0]["content"] if len(convo) == 1 else "\n\n".join(
        f"<{m['role']}>\n{m['content']}\n</{m['role']}>" for m in convo) + "\n\nReply as the assistant to the last user turn."
    cmd = ["claude", "-p", "--model", model, "--tools", "", "--system-prompt", system, "--setting-sources", "",
           "--strict-mcp-config", "--no-session-persistence", "--disable-slash-commands", "--output-format", "json"]
    for attempt in range(3):
        # Every prompt is used once, so a cache write (billed at 2x input for Claude Code's 1-hour cache) is pure waste.
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=tempfile.gettempdir(), timeout=900,
                           env={**os.environ, "DISABLE_PROMPT_CACHING": "1"})
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            d = {"is_error": True, "result": (r.stderr or r.stdout)[:300]}
        if not d.get("is_error"):
            break
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"claude -p failed: {str(d.get('result'))[:300]}")
    u = d.get("usage", {})
    return {"choices": [{"message": {"content": d.get("result") or ""},
                         "finish_reason": "length" if d.get("stop_reason") == "max_tokens" else "stop"}],
            "usage": {"prompt_tokens": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                      + u.get("cache_read_input_tokens", 0),
                      "completion_tokens": u.get("output_tokens", 0), "cost": d.get("total_cost_usd", 0.0)}}


def run_one(job, model, max_tokens, key, log):
    path, brief, inputs, outputs = plan(job)
    if not outputs:
        return f"skip  {job} (outputs already exist)"
    # Blind IDs for this round, used only to check the reply is complete; key.json itself is never sent to the model.
    key_file = os.path.join(os.path.dirname(os.path.abspath(path)), "key.json")
    ids = json.load(open(key_file)).get("key", {}).keys() if os.path.isfile(key_file) else ()
    messages = build_messages(brief, inputs, outputs)
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    err = None
    for attempt in range(3):
        resp = call(model, messages, max_tokens, key)
        u = resp.get("usage", {})
        for k in usage:
            usage[k] += u.get(k, 0) or 0
        choice = resp["choices"][0]
        text = choice["message"].get("content") or ""
        try:
            if choice.get("finish_reason") == "length":
                raise ValueError(f"reply cut off at {max_tokens} tokens")
            if len(outputs) == 1:
                files = {outputs[0]: strip_fences(text)}
            else:
                files = json.loads(re.search(r"\{.*\}", strip_fences(text), re.S).group(0))["files"]
                missing = [o for o in outputs if o not in files]
                if missing:
                    raise ValueError(f"missing outputs: {missing}")
            for p, c in files.items():
                if p in outputs:
                    check(p, c, ids)
            for p in outputs:
                open(p, "w").write(files[p].strip() + "\n")
            err = None
            break
        except (ValueError, KeyError, AttributeError, json.JSONDecodeError) as e:
            err = str(e)
            if choice.get("finish_reason") == "length":
                # Reasoning models spend hidden tokens before answering: ask again fresh with twice the room.
                max_tokens *= 2
                continue
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": f"That answer was not usable ({err}). Answer again, "
                                                               "exactly in the required format."}]
    rec = {"job": job, "model": model, **usage, "ok": err is None, "error": err, "time": time.strftime("%H:%M:%S")}
    with open(log, "a") as f:
        f.write(json.dumps(rec) + "\n")
    tok = usage["prompt_tokens"] + usage["completion_tokens"]
    return f"{'ok   ' if err is None else 'FAIL '} {job}  {tok} tok  ${usage['cost']:.5f}" + (f"  ({err})" if err else "")


def run_many(jobs, a, key, out=None):
    out = out or (lambda s: print(s, flush=True))
    totals = []
    with cf.ThreadPoolExecutor(a["concurrency"]) as ex:
        def safe(j):
            try:
                return run_one(j, a["model"], a["max_tokens"], key, a["log"])
            except Exception as e:  # one bad job must not stop the others
                return f"FAIL  {j}  ({type(e).__name__}: {str(e)[:200]})"
        for line in ex.map(safe, jobs):
            out(line)
            totals.append(line)
    return totals


def court(trials, slugs, a, key, out=None):
    out = out or (lambda s: print(s, flush=True))
    state = os.path.join(trials, ".runner-launched.txt")
    for _ in range(12):
        ready = subprocess.run(["bash", os.path.join(HERE, "advance.sh"), trials, state, *slugs],
                               capture_output=True, text=True).stdout.split()
        briefs = [b for b in ready if b.endswith(".md")]
        if not briefs:
            out("all trials finished")
            return
        run_many(briefs, a, key, out)


def main():
    argv = sys.argv[1:]
    a = {"model": None, "concurrency": 8, "max_tokens": 16000, "log": "usage.jsonl", "dry": False}
    rest = []
    i = 0
    while i < len(argv):
        k = argv[i]
        if k in ("--model", "--concurrency", "--max-tokens", "--log"):
            a[k[2:].replace("-", "_")] = argv[i + 1] if k in ("--model", "--log") else int(argv[i + 1])
            i += 2
        elif k == "--dry-run":
            a["dry"] = True
            i += 1
        else:
            rest.append(k)
            i += 1
    if not rest or (not a["model"] and not a["dry"]):
        sys.exit(__doc__)
    if a["dry"]:
        jobs = rest[1:] if rest[0] == "--court" else rest
        for j in jobs:
            path, brief, inputs, outputs = plan(j)
            words = len(brief.split()) + sum(len(open(p).read().split()) for p in inputs)
            print(f"{j}\n  inputs:  {inputs}\n  outputs: {outputs}\n  ~{int(words * 1.35)} prompt tokens")
        return
    key = api_key(a["model"])
    if rest[0] == "--court":
        court(rest[1], rest[2:], a, key)
    else:
        run_many(rest, a, key)
    try:
        recs = [json.loads(l) for l in open(a["log"])]
        print(f"log {a['log']}: {sum(r['prompt_tokens'] + r['completion_tokens'] for r in recs)} tokens, "
              f"${sum(r['cost'] for r in recs):.4f} total so far")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
