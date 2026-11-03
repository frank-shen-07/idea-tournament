#!/usr/bin/env python3
"""Build LEADERBOARD.md (and scores.png if matplotlib is installed) from <lab>/scores.json.

scores.json: {"slug": {"rubric": 0-60, "judges": 0-30, "not_guilty": 0-6 or null, "verdict": "NOT GUILTY"}}
Usage: python3 leaderboard.py idea-lab [--jury 6]
"""
import json, os, sys

lab = sys.argv[1] if len(sys.argv) > 1 else "idea-lab"
jury = int(sys.argv[sys.argv.index("--jury") + 1]) if "--jury" in sys.argv else 6
data = json.load(open(os.path.join(lab, "scores.json")))

rows = []
for slug, d in data.items():
    r, j, ng = d["rubric"], d["judges"], d.get("not_guilty")
    if ng is None:
        parts = (50 * r / 60, 50 * j / 30, 0)
    else:
        parts = (40 * r / 60, 30 * j / 30, 30 * ng / jury)
    rows.append((slug, r, j, ng, d.get("verdict", "not tried" if ng is None else ""), parts, sum(parts)))
rows.sort(key=lambda x: -x[6])

out = ["# Idea leaderboard", "",
       f"Composite: tried = 40% rubric (/60) + 30% judge panel (/30) + 30% not-guilty share ({jury}-juror court); "
       "not tried = 50% rubric + 50% judge panel.", "",
       "| # | Idea | Rubric /60 | Judges /30 | Court | Composite |", "|---|---|---|---|---|---|"]
for i, (s, r, j, ng, v, _, c) in enumerate(rows, 1):
    court = f"{v}, {ng}/{jury} not guilty" if ng is not None else "not tried"
    out.append(f"| {i} | {s} | {r} | {j} | {court} | {c:.1f} |")
open(os.path.join(lab, "LEADERBOARD.md"), "w").write("\n".join(out) + "\n")
print("\n".join(out))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit(0)

R, bg = rows[::-1], "#fcfcfb"
fig, ax = plt.subplots(figsize=(10, max(3, 0.45 * len(R) + 1.5)), facecolor=bg)
ax.set_facecolor(bg)
left = [0] * len(R)
for i, (lab_, col) in enumerate([("Rubric", "#2a78d6"), ("Judge panel", "#eb6834"), ("Court (not-guilty share)", "#1baf7a")]):
    vals = [r[5][i] for r in R]
    ax.barh(range(len(R)), vals, left=left, color=col, label=lab_, height=0.7, edgecolor=bg, linewidth=2)
    left = [a + b for a, b in zip(left, vals)]
for k, r in enumerate(R):
    ax.text(r[6] + 0.8, k, f"{r[6]:.1f}  {r[4]}", va="center", fontsize=8.5, color="#555")
ax.set_yticks(range(len(R)))
ax.set_yticklabels([r[0] for r in R], fontsize=9)
for t, r in zip(ax.get_yticklabels(), R):
    if r[3] is None:
        t.set_color("#777")
ax.set_xlim(0, 100)
ax.set_xlabel("Composite score (0–100)", color="#555")
ax.set_title("Idea scores\nTried: 40% rubric + 30% judges + 30% court · Not tried (grey names): 50% rubric + 50% judges",
             fontsize=11, loc="left")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="x", color="#e5e5e2", linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3, frameon=False, fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(lab, "scores.png"), dpi=150)
