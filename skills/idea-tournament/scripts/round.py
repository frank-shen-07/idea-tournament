#!/usr/bin/env python3
"""Run one whole tournament round in one command: write -> score blind -> head-to-head -> trial -> leaderboard.

The organiser (the Claude Code session) only starts this and reads the summary it prints, so a round costs it a
few turns instead of dozens. Every job runs through run_jobs.py (Claude via `claude -p`, or an OpenRouter model),
with format checks, retries and exact token/cost logging to <lab>/usage-round<N>.jsonl.

Usage: python3 round.py <lab> <round> [options]
  --ideas  MODEL   new ideas + revision          (default claude:sonnet)
  --score  MODEL   blind rubric + judge scoring  (default claude:sonnet)
  --pairs  MODEL   head-to-heads                 (default z-ai/glm-5.3-flash)
  --court  MODEL   trials                        (default z-ai/glm-5.3-flash)
  --new 3  --scorers 3  --pair-judges 1  --max-trials 2  --no-revise
MODEL is claude:<alias> (e.g. claude:sonnet, claude:haiku) or an OpenRouter model id.

Rules applied (see SKILL.md): at least --new brand-new ideas; the leader is revised unless its family was revised in
both previous rounds; a challenger (the revision, or a new idea scoring above the leader) replaces the leader only by
winning the blind head-to-head with no lower composite; every untried idea in the top 3 goes on trial (up to
--max-trials), with a retrial on a different seed when the jury splits evenly.
"""
import json, os, re, subprocess, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_jobs  # noqa: E402

COURT = os.path.join(HERE, "..", "court", "court.py")


def sh(*args, cwd=None):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        sys.exit(f"failed: {' '.join(args[:2])}\n{r.stderr or r.stdout}")
    return r.stdout


def composite(d, jury=6):
    if d.get("rubric") is None or d.get("judges") is None:
        return None
    ng = d.get("not_guilty")
    if ng is None:
        return 50 * d["rubric"] / 60 + 50 * d["judges"] / 30
    return 40 * d["rubric"] / 60 + 30 * d["judges"] / 30 + 30 * ng / d.get("jurors", jury)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32].rstrip("-")


class Runner:
    """Runs job batches on a model, logging to one usage file; job lines go to the round log, not the screen."""

    def __init__(self, lab, rnd):
        self.log = os.path.join(lab, f"usage-round{rnd}.jsonl")
        self.out = open(os.path.join(lab, f"round{rnd}.log"), "a")
        self.lock = threading.Lock()

    def _opts(self, model):
        return {"model": model, "concurrency": 8, "max_tokens": 16000, "log": self.log}

    def jobs(self, model, jobs):
        if not jobs:
            return []
        lines = run_jobs.run_many(jobs, self._opts(model), run_jobs.api_key(model), self._write)
        return [l for l in lines if l.startswith("FAIL")]

    def court(self, model, trials, slugs):
        run_jobs.court(trials, slugs, self._opts(model), run_jobs.api_key(model), self._write)

    def _write(self, s):
        with self.lock:
            self.out.write(s + "\n")
            self.out.flush()


def parallel(*fns):
    res = [None] * len(fns)
    ts = [threading.Thread(target=lambda i=i, f=f: res.__setitem__(i, f())) for i, f in enumerate(fns)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return res


def conditions(lab, slug):
    """The judge's 'Conditions for acquittal' from the idea's latest trial, used as revision notes."""
    latest = os.path.join(lab, "trials", slug, ".court", "LATEST")
    if not os.path.exists(latest):
        return ""
    v = os.path.join(lab, "trials", slug, open(latest).read().strip(), "VERDICT.md")
    if not os.path.exists(v):
        return ""
    m = re.search(r"## Conditions for acquittal\n(.*?)(?=\n## |\Z)", open(v).read(), re.S)
    return m.group(0).strip() if m else ""


def preflight(M):
    """Before anything is spent: every OpenRouter role needs a working key, and Claude roles need the claude CLI."""
    import shutil
    import openrouter_key as ok_
    if any(m.startswith("claude:") for m in M.values()) and not shutil.which("claude"):
        sys.exit("The claude CLI is not on PATH; Claude roles need it (or pass OpenRouter models for every role).")
    roles = [r for r, m in M.items() if not m.startswith("claude:")]
    if not roles:
        return
    key = ok_.current_key()
    if not key and sys.stdin.isatty():  # started by a person in a terminal: ask right here, at a hidden prompt
        print(f"No OpenRouter key yet (needed for: {', '.join(roles)}).")
        ok_.setup()
        key = ok_.current_key()
    if not key:
        here = os.path.join(HERE, "openrouter_key.py")
        sys.exit("STOPPED before spending anything: no OpenRouter key, needed for " + ", ".join(roles) + ".\n"
                 f"The user should run this in their own terminal (never paste a key into a chat):\n  python3 {here}\n"
                 "Or run every role on Claude: " + " ".join(f"--{r} claude:sonnet" for r in roles))
    good, msg = ok_.verify(key)
    if good is False:
        sys.exit(f"STOPPED before spending anything: {msg} Fix it with: python3 {os.path.join(HERE, 'openrouter_key.py')}")


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    lab, rnd = os.path.abspath(a[0]), int(a[1])

    def opt(k, d):
        return a[a.index(k) + 1] if k in a else d

    M = {"ideas": opt("--ideas", "claude:sonnet"), "score": opt("--score", "claude:sonnet"),
         "pairs": opt("--pairs", "z-ai/glm-5.3-flash"), "court": opt("--court", "z-ai/glm-5.3-flash")}
    preflight(M)
    n_new, n_scorers = int(opt("--new", 3)), int(opt("--scorers", 3))
    pair_judges, max_trials = int(opt("--pair-judges", 1)), int(opt("--max-trials", 2))
    run = Runner(lab, rnd)
    sp = os.path.join(lab, "scores.json")
    S = json.load(open(sp))
    anchors = list(S.get("_anchors", {}).get("rubric", {}))
    events = []

    def board():
        return [s for s, d in S.items() if not s.startswith("_") and os.path.exists(os.path.join(lab, "ideas", f"{s}.card.md"))]

    def ranked():
        rows = [(s, composite(S[s])) for s in board() if composite(S[s]) is not None]
        return [s for s, _ in sorted(rows, key=lambda x: -x[1])]

    stp = os.path.join(lab, f"round{rnd}.state.json")  # progress, so a re-run resumes after the last finished step
    st = json.load(open(stp)) if os.path.exists(stp) else {"done": []}

    def save(step, **kw):
        st.update(kw)
        st["done"].append(step)
        json.dump(st, open(stp, "w"), indent=1)

    fam = lambda s: S.get(s, {}).get("family") or s  # noqa: E731
    letters = "abcdefg"[:n_scorers]
    packed = os.path.join(lab, "blind", f"round{rnd}", "packed-score.md")
    pairs = [tuple(p) for p in st.get("pairs", [])]  # (name, incumbent, challenger)

    def setup_pair(inc, chal):
        name = f"r{rnd}-{chal}-vs-{inc}"
        out = sh(os.path.join(HERE, "pairwise.py"), "setup", lab, name, inc, chal, "--judges", str(pair_judges))
        pairs.append((name, inc, chal))
        return [l for l in out.split() if l.endswith(".md")]


    # ---- A. new ideas (+ revision of the leader) ----
    if "A" in st["done"]:
        leader, new, rev, events = st["leader"], st["new"], st["rev"], st["events"]
    else:
        leader = next((s for s in ranked() if s not in anchors), None)
        revs = S.setdefault("_revisions", {})
        revise = leader if leader and "--no-revise" not in a and not (
            revs.get(str(rnd - 1)) == fam(leader) and revs.get(str(rnd - 2)) == fam(leader)) else None
        pack_args = ["ideas", lab, str(rnd), str(n_new)]
        if revise:
            notes = conditions(lab, revise)
            np_ = os.path.join(lab, "ideas", f"notes-round{rnd}.md")
            open(np_, "w").write(notes or "No trial notes yet: strengthen the weakest rubric dimensions.")
            pack_args += ["--revise", revise, "--notes", np_]
        sh(os.path.join(HERE, "pack.py"), *pack_args)
        fails = run.jobs(M["ideas"], [os.path.join(lab, "ideas", f"packed-ideas-round{rnd}.md")])
        new = []
        for i in range(1, n_new + 1):
            p = os.path.join(lab, "ideas", f"n{rnd}-{i}.card.md")
            if not os.path.exists(p):
                continue
            m = re.match(r'\s*Build "([^"]+)"', open(p).read())
            slug = f"n{rnd}-" + (slugify(m.group(1)) if m else str(i))
            os.rename(p, os.path.join(lab, "ideas", f"{slug}.card.md"))
            S.setdefault(slug, {})["family"] = slug
            new.append(slug)
        rev = f"{revise}-rev{rnd}" if revise else None
        if rev and os.path.exists(os.path.join(lab, "ideas", f"{rev}.card.md")):
            S.setdefault(rev, {})["family"] = fam(revise)
            revs[str(rnd)] = fam(revise)
        else:
            rev = None
        for s in board():
            S[s].setdefault("family", s)
        json.dump(S, open(sp, "w"), indent=1)
        events.append(f"ideas: {len(new)} new ({', '.join(new) or 'none'})" + (f"; revision {rev}" if rev else "")
                      + (f"; FAILED: {fails}" if fails else ""))

        save("A", leader=leader, new=new, rev=rev, events=events)

    # ---- B. blind scoring, with the revision's head-to-head in parallel ----
    if "B" in st["done"]:
        drift, events = st["drift"], st["events"]
    else:
        slugs = [s for s in board() if s not in anchors]
        sh(os.path.join(HERE, "blind.py"), lab, str(rnd), *slugs, "--anchors", *anchors)
        sh(os.path.join(HERE, "pack.py"), "score", lab, str(rnd))
        rev_briefs = setup_pair(leader, rev) if rev else []
        score_fails, _ = parallel(lambda: run.jobs(M["score"], [f"{packed}:{l}" for l in letters]),
                                  lambda: run.jobs(M["pairs"], rev_briefs))
        for l in letters:
            rp = os.path.join(lab, "scores", f"round{rnd}", f"reply-{l}.json")
            if os.path.exists(rp):
                subprocess.run([sys.executable, os.path.join(HERE, "record.py"), "score", lab, str(rnd), l],
                               stdin=open(rp), capture_output=True)
        drift = sh(os.path.join(HERE, "scores.py"), lab, str(rnd), "rubric")
        drift += sh(os.path.join(HERE, "scores.py"), lab, str(rnd), "judges")
        S = json.load(open(sp))
        events.append(f"scoring: {n_scorers - len(score_fails)}/{n_scorers} scorers ok" +
                      (f"; FAILED: {score_fails}" if score_fails else ""))

        save("B", drift=drift, events=events, pairs=pairs)

    # ---- C. head-to-heads: the revision, and any new idea scoring above the leader ----
    if "C" in st["done"]:
        events = st["events"]
    else:
        lead_c = composite(S[leader]) if leader else None
        extra = [s for s in new if lead_c is not None and (composite(S[s]) or 0) > lead_c]
        run.jobs(M["pairs"], [b for s in extra for b in setup_pair(leader, s)])
        for name, inc, chal in pairs:
            out = sh(os.path.join(HERE, "pairwise.py"), "tally", lab, name)
            won = "challenger replaces" in out
            cc, ci = composite(S[chal]) or 0, composite(S[inc]) or 0
            ok = won and cc >= ci
            S[chal]["h2h"] = {"vs": inc, "round": rnd, "won_pick": won, "replaces": ok}
            if ok:
                S["_leader"] = chal
            events.append(f"head-to-head {chal} vs {inc}: " + (
                "challenger wins and replaces the leader" if ok else
                f"challenger won the picks but scores lower ({cc:.1f} vs {ci:.1f}); leader stays"
                if won else "leader stays"))
        json.dump(S, open(sp, "w"), indent=1)

        save("C", events=events, pairs=pairs)

    # ---- D. trials: every untried idea in the top 3 (and a head-to-head winner) ----
    top3 = ranked()[:3]
    want = [s for s in top3 if S[s].get("not_guilty") is None]
    want += [s for _, _, c in pairs if S[c].get("h2h", {}).get("replaces") and S[c].get("not_guilty") is None and c not in want]
    want = want[:max_trials]
    trials = os.path.join(lab, "trials")
    id_of = {v: k for k, v in json.load(open(os.path.join(lab, "blind", f"round{rnd}", "key.json")))["key"].items()}

    def open_trial(s, seed):
        d = os.path.join(trials, s)
        os.makedirs(os.path.join(d, ".court"), exist_ok=True)
        case = open(os.path.join(lab, "blind", f"round{rnd}", f"{id_of[s]}.md")).read() + "\n" + open(
            os.path.join(lab, "context.md")).read()
        open(os.path.join(d, ".court", "case.md"), "w").write(case)
        sh(COURT, "init", "--case-file", ".court/case.md", "--quick", "--seed", str(seed), cwd=d)

    def tally(s):
        latest = open(os.path.join(trials, s, ".court", "LATEST")).read().strip()
        t = json.load(open(os.path.join(trials, s, latest, "tally.json")))
        return t["guilty"], t["not_guilty"]

    if want:
        for s in want:
            if s not in st.get("opened", []):  # a resumed round continues the trial it already opened
                open_trial(s, 9)
                st.setdefault("opened", []).append(s)
                json.dump(st, open(stp, "w"), indent=1)
        run.court(M["court"], trials, want)
        votes = {s: tally(s) for s in want}
        hung = [s for s in want if votes[s][0] == votes[s][1]]
        if hung:  # retrial on a new seed; votes are added
            for s in hung:
                if s not in st.get("reopened", []):
                    open_trial(s, 10)
                    st.setdefault("reopened", []).append(s)
                    json.dump(st, open(stp, "w"), indent=1)
            run.court(M["court"], trials, hung)
            for s in hung:
                g, n = tally(s)
                votes[s] = (votes[s][0] + g, votes[s][1] + n)
        for s, (g, n) in votes.items():
            verdict = "NOT GUILTY" if n > g else "GUILTY" if g > n else "HUNG JURY"
            S[s].update(verdict=verdict, not_guilty=n, jurors=g + n)
            events.append(f"trial {s}: {verdict} {n}-{g}" + (" (after retrial)" if g + n > 6 else ""))
    else:
        events.append("trials: none needed (top 3 all tried)")
    json.dump(S, open(sp, "w"), indent=1)

    # ---- E. leaderboard and summary ----
    board_md = sh(os.path.join(HERE, "leaderboard.py"), lab, "--round", str(rnd))
    rows = [l for l in board_md.splitlines() if l.startswith("| ") and not l.startswith("| #")][:5]
    print(f"ROUND {rnd} ({lab})")
    print("\n".join(rows))
    for e in events:
        print("-", e)
    print("-", " ".join(l.strip() for l in drift.splitlines() if "drift" in l))
    fam_top = [fam(r.split("|")[2].strip()) for r in rows[:3]]
    if len(set(fam_top)) == 1:
        print(f"- warning: the top 3 share one family ({fam_top[0]})")
    steps = {}
    for l in open(run.log):
        r = json.loads(l)
        j = r["job"]
        step = ("ideas" if "packed-ideas" in j else "scoring" if "packed-score" in j else
                "head-to-head" if "/pairwise/" in j else "court" if "/.court/" in j else "other")
        k = (step, r["model"])
        b = steps.setdefault(k, [0, 0, 0.0, 0])
        b[0] += 1
        b[1] += r["prompt_tokens"] + r["completion_tokens"]
        b[2] += r["cost"] or 0
        b[3] += not r["ok"]
    print("cost:")
    for (step, model), (n, tok, usd, bad) in steps.items():
        print(f"  {step:13}{model:22}{n:>3} jobs {tok:>8} tok  ${usd:.4f}" + (f"  {bad} failed" if bad else ""))
    print(f"  {'TOTAL':35}{sum(v[0] for v in steps.values()):>3} jobs {sum(v[1] for v in steps.values()):>8} tok  "
          f"${sum(v[2] for v in steps.values()):.4f}")
    print(f"chart: {lab}/scores.svg")
    print(f"details: {run.out.name}, {run.log}, {lab}/LEADERBOARD.md")


if __name__ == "__main__":
    main()
