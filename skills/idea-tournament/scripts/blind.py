#!/usr/bin/env python3
"""Make blind copies of idea cards for one scoring round.

Strips names, version history and trial talk, gives each card a random ID, and enforces a word cap so
longer cards can't win on detail. The ID -> slug key is written next to the cards; never show it to scorers.

Usage: python3 blind.py <lab> <round> <slug>... [--anchors <slug>...] [--max-words 450] [--allow-long]
Writes: <lab>/blind/round<N>/<ID>.md and key.json
"""
import json, os, random, re, string, sys

STRIP_PAREN = re.compile(r"\s*\([^()]*\b(version|revised|revision|v\d+|trial|iteration|improved|"
                         r"changes the framing|combines|after \w+ (trials|rounds))\b[^()]*\)", re.I)
# Sentences about the idea's own history (earlier versions, trials, scores). Domain words like "verdict" or
# "court" stay: they can be part of the idea itself. Only whole sentences are removed, never whole bullets.
HISTORY = re.compile(r"(?i)\b(previous|earlier|last|third|fourth|second) (version|trial|round)s?\b|\bjur(y|or|ors)\b|"
                     r"\bacquitt|\b(found|voted) (not )?guilty\b|\brubric\b|\b\d+/60\b|\bscored \d")
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(])")
NAME = re.compile(r'^Build "([^"]+)"', re.M)


def strip_card(text, new_name):
    m = NAME.search(text)
    name = m.group(1) if m else None
    text = STRIP_PAREN.sub("", text)
    lines = []
    for l in text.splitlines():
        if HISTORY.search(l):
            l = " ".join(s for s in SENT.split(l) if not HISTORY.search(s))
        lines.append(l)
    text = "\n".join(lines)
    if name:
        base = re.sub(r"\s*[:(\-–].*$", "", name).strip()  # "Rent Rebuttal: Counter-Offer" -> "Rent Rebuttal"
        for n in sorted({name, base}, key=len, reverse=True):
            if n:
                text = text.replace(n, new_name)
    return text.strip() + "\n"


def new_ids(n, taken=()):
    ids = set()
    while len(ids) < n:
        i = "".join(random.choices(string.ascii_uppercase, k=3))
        if i not in taken:
            ids.add(i)
    return list(ids)


def main():
    a = sys.argv[1:]
    if len(a) < 3:
        sys.exit(__doc__)
    lab, rnd = a[0], a[1]
    cap = int(a[a.index("--max-words") + 1]) if "--max-words" in a else 450
    allow_long = "--allow-long" in a
    rest = [x for x in a[2:] if x not in ("--allow-long",)]
    if "--max-words" in rest:
        i = rest.index("--max-words"); del rest[i:i + 2]
    anchors = []
    if "--anchors" in rest:
        i = rest.index("--anchors"); anchors = rest[i + 1:]; rest = rest[:i]
    slugs = rest + [s for s in anchors if s not in rest]

    out = os.path.join(lab, "blind", f"round{rnd}")
    os.makedirs(out, exist_ok=True)
    ids = new_ids(len(slugs))
    random.shuffle(ids)
    key, long_cards = {}, []
    for slug, i in zip(slugs, ids):
        text = strip_card(open(os.path.join(lab, "ideas", f"{slug}.card.md")).read(), f"Idea {i}")
        words = len(text.split())
        if words > cap:
            long_cards.append((slug, words))
        open(os.path.join(out, f"{i}.md"), "w").write(text)
        key[i] = slug
    json.dump({"key": key, "anchors": anchors, "max_words": cap}, open(os.path.join(out, "key.json"), "w"), indent=1)
    for slug, w in long_cards:
        print(f"OVER CAP: {slug} has {w} words (cap {cap}). Shorten the card and re-run.", file=sys.stderr)
    if long_cards and not allow_long:
        sys.exit(1)
    for i in sorted(key):
        print(os.path.join(out, f"{i}.md"))


if __name__ == "__main__":
    main()
