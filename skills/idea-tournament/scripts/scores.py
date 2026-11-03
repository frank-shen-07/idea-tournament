#!/usr/bin/env python3
"""Combine several fresh scorers' blind scores for a round, correct drift with anchor cards, update scores.json.

Each scorer writes one JSON file: <lab>/scores/round<N>/<kind>-<anything>.json  as  {"<ID>": {"total": 44, ...}, ...}
(kind = rubric or judges). IDs come from blind.py's key.json for the same round.

Drift: anchors are fixed cards re-scored every round. Their first-ever median is the baseline. A round's drift is the
median of (anchor score now - baseline); every idea's score in that round is corrected by subtracting it.

Usage: python3 scores.py <lab> <round> <kind>
"""
import glob, json, os, statistics, sys

lab, rnd, kind = sys.argv[1], sys.argv[2], sys.argv[3]
meta = json.load(open(os.path.join(lab, "blind", f"round{rnd}", "key.json")))
key, anchors = meta["key"], meta["anchors"]
files = sorted(glob.glob(os.path.join(lab, "scores", f"round{rnd}", f"{kind}-*.json")))
if not files:
    sys.exit(f"no {kind}-*.json files in {lab}/scores/round{rnd}/")

per = {}
for f in files:
    for i, v in json.load(open(f)).items():
        if i in key:
            per.setdefault(key[i], []).append(v["total"] if isinstance(v, dict) else v)
raw = {s: statistics.median(v) for s, v in per.items()}
spread = {s: max(v) - min(v) for s, v in per.items()}

path = os.path.join(lab, "scores.json")
data = json.load(open(path)) if os.path.exists(path) else {}
base = data.setdefault("_anchors", {}).setdefault(kind, {})
deltas = []
for s in anchors:
    if s not in raw:
        continue
    if s in base:
        deltas.append(raw[s] - base[s])
    else:
        base[s] = raw[s]
drift = statistics.median(deltas) if deltas else 0.0

print(f"{kind} round {rnd}: {len(files)} scorers, anchor drift {drift:+.1f}")
for s in sorted(raw, key=lambda s: -raw[s]):
    corrected = round(raw[s] - drift, 1)
    e = data.setdefault(s, {"not_guilty": None, "verdict": "not tried"})
    e[kind], e[f"{kind}_raw"], e[f"{kind}_spread"] = corrected, raw[s], spread[s]
    tag = " (anchor)" if s in anchors else ""
    print(f"  {s:32s} raw {raw[s]:5.1f}  spread {spread[s]:4.1f}  corrected {corrected:5.1f}{tag}")
json.dump(data, open(path, "w"), indent=1)
