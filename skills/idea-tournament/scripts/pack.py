#!/usr/bin/env python3
"""Pack everything a scorer needs into ONE file, so each agent opens one file and replies (2 steps, not 6+).

score:  python3 pack.py score <lab> <round>
        -> <lab>/blind/round<N>/packed-score.md  (instructions + rubric + context + every blind card)
        Launch each scorer with the prompt '<path> <letter>'; it writes scores/round<N>/reply-<letter>.json.
        Then: python3 record.py score <lab> <round> <letter> < scores/round<N>/reply-<letter>.json
ideas:  python3 pack.py ideas <lab> <round> <n-new> [--revise <slug> --notes <file>] [--max-words 450]
        -> <lab>/ideas/packed-ideas-round<N>.md  (task + context + every idea on the board as one-liners +
        the leader's card + optional notes); the idea-writer agent writes the cards it names.
"""
import glob, os, sys

SCORE_TASK = """# Task: score hackathon ideas blind (rubric + judge panel, one pass)

Everything you need is in this file. Do not open any other file.

Rules for both scores:
- Score the THEORETICAL QUALITY of each idea as if built as described.
- Every data field listed in the context counts as available; deduct Feasibility only for data the context does not list.
- No deductions for illustrative numbers or unconfirmed fields.
- Apply the rubric's calibration rules (novelty cap, adoption in Impact, build effort in Feasibility).
- Ignore length, polish and any self-assessment in the cards. Be calibrated and use the full range.

1) Rubric: Novelty, Feasibility, Scalability, Impact, Demo-ability, Domain Fit, each /10 (rubric below).
2) Judge panel: predict the event judges' scores, 1-10 each on the event's judging criteria (see context), e.g.
   useful, explained (how clearly it can be explained and demoed in 3 minutes) and attention.

Write ONE JSON object, covering every card ID, to {out} (your prompt gives your <letter>), then reply "done":
{"rubric": {"<ID>": {"novelty": n, "feasibility": n, "scalability": n, "impact": n, "demo": n, "fit": n, "total": n}},
 "judges": {"<ID>": {"useful": n, "explained": n, "attention": n, "total": n}}}
"""


HERE = os.path.dirname(os.path.abspath(__file__))
RUBRIC = os.path.join(HERE, "..", "rubric.md")

CARD_FORMAT = """Build "<Name>" at <event>: <one sentence: who does what and what they see>.

## The idea
- **Who it is for:** a real person with a real decision
- **What the user sees:** the screen / demo moment (mark made-up numbers "(illustrative)")
- **Data:** only fields listed in the context, quoted
- **Method:** the technique, with data gaps stated
- **Build:** what gets built in the time available
- **First hour on the day:** what to check first, the pass mark, and the fallback if it fails"""


def first_line(path):
    with open(path) as f:
        return f.readline().strip()


def ideas(lab, rnd, n, revise, notes, cap):
    board = sorted(glob.glob(os.path.join(lab, "ideas", "*.card.md")))
    slugs = [os.path.basename(p)[:-8] for p in board if not p.endswith(".long.md")]
    lines = [f"- {s}: {first_line(os.path.join(lab, 'ideas', s + '.card.md'))}" for s in slugs]
    out_paths = [os.path.abspath(os.path.join(lab, "ideas", f"n{rnd}-{i}.card.md")) for i in range(1, n + 1)]
    task = [f"# Task: write {n} new hackathon idea card(s)\n",
            "Everything you need is in this file. Do not open any other file.\n",
            f"Write {n} ideas that are NEW: each must differ from every idea on the board below in its core "
            "(a different user, decision or technique, not a reframing of an existing one). Aim them at what the "
            "event's judges score. Use only data the context lists.",
            f"Each card at most {cap} words, in exactly this format:\n\n```\n{CARD_FORMAT}\n```\n",
            "Write them to these paths (choose a short name per idea; keep the file paths as given):"]
    task += [f"- {p}" for p in out_paths]
    if revise:
        rp = os.path.abspath(os.path.join(lab, "ideas", f"{revise}-rev{rnd}.card.md"))
        task += [f"\nAlso write ONE revision of `{revise}` (its card is below) to {rp}, fixing the weaknesses in "
                 "the notes. Change the idea, not just the wording; keep what works."]
    parts = task + ["\n# Event context\n", open(os.path.join(lab, "context.md")).read().strip(),
                    "\n# Ideas already on the board (do not repeat their core)\n"] + lines
    if revise:
        parts += [f"\n# Card to revise: {revise}\n", open(os.path.join(lab, "ideas", revise + ".card.md")).read().strip()]
    if notes:
        parts += ["\n# Notes from scorers and judges\n", open(notes).read().strip()]
    out = os.path.join(lab, "ideas", f"packed-ideas-round{rnd}.md")
    open(out, "w").write("\n".join(parts) + "\n")
    print(os.path.abspath(out), f"({len(open(out).read().split())} words)")


def main():
    a = sys.argv[1:]
    if len(a) >= 4 and a[0] == "ideas":
        opt = lambda k: a[a.index(k) + 1] if k in a else None
        return ideas(a[1], a[2], int(a[3]), opt("--revise"), opt("--notes"), int(opt("--max-words") or 450))
    if len(a) < 3 or a[0] != "score":
        sys.exit(__doc__)
    lab, rnd = a[1], a[2]
    d = os.path.join(lab, "blind", f"round{rnd}")
    reply = os.path.abspath(os.path.join(lab, "scores", f"round{rnd}", "reply-<letter>.json"))
    os.makedirs(os.path.dirname(reply), exist_ok=True)
    parts = [SCORE_TASK.replace("{out}", reply), "# Rubric\n", open(RUBRIC).read().strip(),
             "\n# Event context\n", open(os.path.join(lab, "context.md")).read().strip(), "\n# Cards\n"]
    for f in sorted(glob.glob(os.path.join(d, "[A-Z][A-Z][A-Z].md"))):
        parts.append(f"## Card {os.path.basename(f)[:-3]}\n\n" + open(f).read().strip() + "\n")
    out = os.path.join(d, "packed-score.md")
    open(out, "w").write("\n".join(parts))
    print(os.path.abspath(out), f"({len(open(out).read().split())} words)")


if __name__ == "__main__":
    main()
