#!/usr/bin/env python3
"""Build LEADERBOARD.md and the chart scores.svg (no dependencies) from <lab>/scores.json.

scores.json: {"slug": {"rubric": 0-60, "judges": 0-30, "not_guilty": n or null, "jurors": 6, "verdict": "NOT GUILTY"}}
Keys starting with "_" (e.g. "_anchors") are ignored.
Usage: python3 leaderboard.py idea-lab [--jury 6] [--round N]
--round N records this round's composites in scores.json "_history", which the chart draws as lines by round.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chart import render  # noqa: E402

lab = sys.argv[1] if len(sys.argv) > 1 else "idea-lab"
jury = int(sys.argv[sys.argv.index("--jury") + 1]) if "--jury" in sys.argv else 6
data = json.load(open(os.path.join(lab, "scores.json")))

rows = []
for slug, d in data.items():
    if slug.startswith("_") or d.get("rubric") is None or d.get("judges") is None:
        continue
    r, j, ng, nj = d["rubric"], d["judges"], d.get("not_guilty"), d.get("jurors", jury)
    if ng is None:
        parts = (50 * r / 60, 50 * j / 30, 0)
    else:
        parts = (40 * r / 60, 30 * j / 30, 30 * ng / nj)
    rows.append((slug, r, j, ng, d.get("verdict", "not tried" if ng is None else ""), parts, sum(parts), nj))
rows.sort(key=lambda x: -x[6])

out = ["# Idea leaderboard", "", "![Idea scores](scores.svg)", "",
       f"Composite: tried = 40% rubric (/60) + 30% judge panel (/30) + 30% not-guilty share (jurors per court, default {jury}; repeat trials add their votes); "
       "not tried = 50% rubric + 50% judge panel.", "",
       "| # | Idea | Rubric /60 | Judges /30 | Court | Composite |", "|---|---|---|---|---|---|"]
for i, (s, r, j, ng, v, _, c, nj) in enumerate(rows, 1):
    court = f"{v}, {ng}/{nj} not guilty" if ng is not None else "not tried"
    out.append(f"| {i} | {s} | {r:g} | {j:g} | {court} | {c:.1f} |")
open(os.path.join(lab, "LEADERBOARD.md"), "w").write("\n".join(out) + "\n")
print("\n".join(out))


if "--round" in sys.argv:
    data.setdefault("_history", {})[sys.argv[sys.argv.index("--round") + 1]] = {r[0]: round(r[6], 1) for r in rows}
    json.dump(data, open(os.path.join(lab, "scores.json"), "w"), indent=1)
render(os.path.join(lab, "scores.svg"), rows, data.get("_history"))
