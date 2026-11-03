#!/usr/bin/env python3
"""Save an agent's JSON reply (read from stdin) where the other scripts expect it.

score: python3 record.py score <lab> <round> <letter>   -> scores/round<N>/rubric-<letter>.json, judges-<letter>.json
pair:  python3 record.py pair <lab> <name> <judge> <order> -> pairwise/<name>/result-j<judge>-o<order>.json
"""
import json, os, re, sys


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)  # tolerate code fences or stray words around the JSON
    if not m:
        sys.exit("no JSON object in reply")
    return json.loads(m.group(0))


a = sys.argv[1:]
reply = parse(sys.stdin.read())
if len(a) == 4 and a[0] == "score":
    d = os.path.join(a[1], "scores", f"round{a[2]}")
    os.makedirs(d, exist_ok=True)
    for kind in ("rubric", "judges"):
        json.dump(reply[kind], open(os.path.join(d, f"{kind}-{a[3]}.json"), "w"))
    print(f"saved {len(reply['rubric'])} rubric and {len(reply['judges'])} judge scores")
elif len(a) == 5 and a[0] == "pair":
    p = os.path.join(a[1], "pairwise", a[2], f"result-j{a[3]}-o{a[4]}.json")
    open(p, "w").write(json.dumps(reply))
    print("saved", p)
else:
    sys.exit(__doc__)
