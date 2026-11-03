#!/usr/bin/env python3
"""Pack everything a scorer needs into ONE file, so each agent opens one file and replies (2 steps, not 6+).

score:  python3 pack.py score <lab> <round> [--rubric <path to hackathon-idea-evaluator SKILL.md>]
        -> <lab>/blind/round<N>/packed-score.md  (instructions + rubric + context + every blind card)
The agent replies with JSON only; save it with:  python3 record.py score <lab> <round> <letter> < reply.json
"""
import glob, os, sys

SCORE_TASK = """# Task: score hackathon ideas blind (rubric + judge panel, one pass)

Everything you need is in this file. Do not open any other file.

Rules for both scores:
- Score the THEORETICAL QUALITY of each idea as if built as described.
- Every data field listed in the context counts as available; deduct Feasibility only for data the context does not list.
- No deductions for illustrative numbers or unconfirmed fields.
- Keep the rubric's other anti-inflation rules (novelty capped at 7 unless both framing and technique are new;
  adoption barriers in Impact; one-day build effort in Feasibility).
- Ignore length, polish and any self-assessment in the cards. Be calibrated and use the full range.

1) Rubric: Novelty, Feasibility, Scalability, Impact, Demo-ability, Domain Fit, each /10 (rubric below).
2) Judge panel: predict the event judges' scores, 1-10 each on the event's judging criteria (see context), e.g.
   useful, explained (how clearly it can be explained and demoed in 3 minutes) and attention.

Reply with ONE JSON object and nothing else, covering every card ID:
{"rubric": {"<ID>": {"novelty": n, "feasibility": n, "scalability": n, "impact": n, "demo": n, "fit": n, "total": n}},
 "judges": {"<ID>": {"useful": n, "explained": n, "attention": n, "total": n}}}
"""


def main():
    a = sys.argv[1:]
    if len(a) < 3 or a[0] != "score":
        sys.exit(__doc__)
    lab, rnd = a[1], a[2]
    rubric = os.path.expanduser(a[a.index("--rubric") + 1] if "--rubric" in a
                                else "~/.claude/skills/hackathon-idea-evaluator/SKILL.md")
    d = os.path.join(lab, "blind", f"round{rnd}")
    parts = [SCORE_TASK, "# Rubric\n", open(rubric).read().split("---", 2)[-1].strip(),
             "\n# Event context\n", open(os.path.join(lab, "context.md")).read().strip(), "\n# Cards\n"]
    for f in sorted(glob.glob(os.path.join(d, "[A-Z][A-Z][A-Z].md"))):
        parts.append(f"## Card {os.path.basename(f)[:-3]}\n\n" + open(f).read().strip() + "\n")
    out = os.path.join(d, "packed-score.md")
    open(out, "w").write("\n".join(parts))
    print(os.path.abspath(out), f"({len(open(out).read().split())} words)")


if __name__ == "__main__":
    main()
