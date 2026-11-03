#!/usr/bin/env python3
"""Blind head-to-head: does a challenger (e.g. a revision) actually beat its incumbent?

setup: python3 pairwise.py setup <lab> <name> <incumbent-slug> <challenger-slug> [--judges 3]
  Writes blind cards and one brief per (judge, order); prints the brief paths. Launch one fresh agent per brief
  with: "Read <brief> and follow it exactly. It is your whole brief."
tally: python3 pairwise.py tally <lab> <name>
  Each judge sees both orders. A judge whose two picks disagree (picked the same position twice) counts as a tie.
  The challenger replaces the incumbent only if it wins a strict majority of judges.
"""
import json, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blind import strip_card, new_ids

BRIEF = """You are judging two hackathon ideas blind. You know nothing about who wrote them or how they were made.

Read only these files:
- Context (the event, judging criteria and available data): {context}
- Option 1: {first}
- Option 2: {second}

Decide which idea would do better with the event's judges, using the judging criteria in the context file, and
which is the better idea to build in the time available. Ignore length, polish and confident wording: judge the
idea, not the writing. Do not read any other file.

Write exactly one line of JSON to {result}:
{{"pick": 1 or 2, "confidence": "low" | "medium" | "high", "reason": "<one sentence>"}}
Then reply with that JSON line only.
"""


def setup(lab, name, inc, chal, judges):
    out = os.path.join(lab, "pairwise", name)
    os.makedirs(out, exist_ok=True)
    a, b = new_ids(2)
    cards = {}
    for slug, i in ((inc, a), (chal, b)):
        p = os.path.join(out, f"{i}.md")
        open(p, "w").write(strip_card(open(os.path.join(lab, "ideas", f"{slug}.card.md")).read(), f"Idea {i}"))
        cards[slug] = p
    ctx = os.path.abspath(os.path.join(lab, "context.md"))
    json.dump({"incumbent": inc, "challenger": chal, "judges": judges}, open(os.path.join(out, "pair.json"), "w"))
    for j in range(1, judges + 1):
        first_is_inc = random.random() < 0.5
        for order in (1, 2):
            inc_first = first_is_inc if order == 1 else not first_is_inc
            f, s = (cards[inc], cards[chal]) if inc_first else (cards[chal], cards[inc])
            res = os.path.abspath(os.path.join(out, f"result-j{j}-o{order}.json"))
            meta = os.path.join(out, f"order-j{j}-o{order}.json")
            json.dump({"option1": inc if inc_first else chal}, open(meta, "w"))
            bp = os.path.join(out, f"brief-j{j}-o{order}.md")
            open(bp, "w").write(BRIEF.format(context=ctx, first=os.path.abspath(f), second=os.path.abspath(s), result=res))
            print(os.path.abspath(bp))


def tally(lab, name):
    out = os.path.join(lab, "pairwise", name)
    pair = json.load(open(os.path.join(out, "pair.json")))
    inc, chal = pair["incumbent"], pair["challenger"]
    votes = {inc: 0, chal: 0, "tie": 0}
    for j in range(1, pair["judges"] + 1):
        picks = []
        for o in (1, 2):
            rp = os.path.join(out, f"result-j{j}-o{o}.json")
            if not os.path.exists(rp):
                print(f"missing {rp}")
                continue
            r = json.loads(open(rp).read().strip().splitlines()[-1])
            first = json.load(open(os.path.join(out, f"order-j{j}-o{o}.json")))["option1"]
            picks.append(first if r["pick"] == 1 else (chal if first == inc else inc))
        if len(picks) == 2:
            votes[picks[0] if picks[0] == picks[1] else "tie"] += 1
    n = pair["judges"]
    winner = chal if votes[chal] > n / 2 else inc
    print(f"{chal} vs {inc}: challenger {votes[chal]}, incumbent {votes[inc]}, position-split ties {votes['tie']} (of {n})")
    print(f"RESULT: {'challenger replaces incumbent' if winner == chal else 'incumbent stays'}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 5 and a[0] == "setup":
        setup(a[1], a[2], a[3], a[4], int(a[a.index("--judges") + 1]) if "--judges" in a else 3)
    elif len(a) == 3 and a[0] == "tally":
        tally(a[1], a[2])
    else:
        sys.exit(__doc__)
