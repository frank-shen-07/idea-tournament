#!/usr/bin/env python3
"""Draw <lab>/scores.svg: the leaderboard as stacked composite bars, plus composite-by-round lines once there are
two or more rounds of history. Plain SVG, no dependencies; opens in any browser and renders on GitHub.

Called by leaderboard.py. Colors are the validated three-slot categorical palette (blue, orange, aqua) with light
and dark steps; aqua is under 3:1 on the light surface, so every bar carries a visible value label and
LEADERBOARD.md is the table view. Hover any bar or point for its numbers.
"""
from html import escape

# role: (light, dark)
INK = {"surface": ("#fcfcfb", "#1a1a19"), "primary": ("#0b0b0b", "#f0efec"), "secondary": ("#52514e", "#c3c2b7"),
       "muted": ("#898781", "#898781"), "grid": ("#e1e0d9", "#2c2c2a"), "axis": ("#c3c2b7", "#383835"),
       "s1": ("#2a78d6", "#3987e5"), "s2": ("#eb6834", "#d95926"), "s3": ("#1baf7a", "#199e70")}
PARTS = [("s1", "Rubric (40% tried, 50% not tried)"), ("s2", "Judge panel (30% / 50%)"), ("s3", "Court: not-guilty share (30%)")]
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def style():
    light = "".join(f"--{k}:{v[0]};" for k, v in INK.items())
    dark = "".join(f"--{k}:{v[1]};" for k, v in INK.items())
    fills = "".join(f".f-{k}{{fill:var(--{k})}}.k-{k}{{stroke:var(--{k})}}" for k in INK)
    return (f"<style>svg{{{light}font-family:{FONT}}}@media (prefers-color-scheme: dark){{svg{{{dark}}}}}"
            f"{fills}text{{font-size:12px}}.t{{font-size:15px;font-weight:600}}.s{{font-size:11.5px}}"
            ".hit{fill:transparent}g.row:hover .hit,g.pt:hover .hit{fill:var(--grid);fill-opacity:.5}</style>")


def end_rounded(x, y, w, h, r=4):
    """A bar segment with a 4px rounded data-end (right) and a square baseline (left)."""
    r = min(r, w / 2, h / 2)
    return (f"M{x:.1f},{y:.1f}H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h - r:.1f}"
            f"Q{x + w:.1f},{y + h:.1f} {x + w - r:.1f},{y + h:.1f}H{x:.1f}Z")


def bars(rows, y0, width):
    """rows: (slug, rubric, judges, not_guilty, verdict, parts, composite, jurors), sorted best first."""
    label_w, end_w = 250, 170
    plot_w = width - label_w - end_w - 24
    x0, row_h, bar_h, gap = label_w, 26, 16, 2
    sx = lambda v: x0 + plot_w * v / 100  # noqa: E731
    out, h = [], row_h * len(rows)
    # legend, one row above the bars
    lx = x0
    for k, name in PARTS:
        out.append(f'<rect x="{lx}" y="{y0}" width="10" height="10" rx="2" class="f-{k}"/>'
                   f'<text x="{lx + 15}" y="{y0 + 9.5}" class="f-secondary s">{escape(name)}</text>')
        lx += 15 + 7 * len(name) + 22
    y0 += 26
    for v in range(0, 101, 20):  # recessive hairline grid and axis labels
        out.append(f'<line x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="{y0 - 4}" y2="{y0 + h}" class="k-grid" stroke-width="1"/>'
                   f'<text x="{sx(v):.1f}" y="{y0 + h + 16}" text-anchor="middle" class="f-muted s">{v}</text>')
    for i, (slug, r, j, ng, verdict, parts, comp, nj) in enumerate(rows):
        y = y0 + i * row_h + (row_h - bar_h) / 2
        tried = ng is not None
        court = f"{verdict}, {ng}/{nj} not guilty" if tried else "not tried (scored as 50% rubric + 50% judges)"
        tip = (f"{slug}: composite {comp:.1f}\nrubric {r:g}/60 → {parts[0]:.1f}\njudges {j:g}/30 → {parts[1]:.1f}\n"
               f"court: {court}" + (f" → {parts[2]:.1f}" if tried else ""))
        out.append(f'<g class="row"><title>{escape(tip)}</title>'
                   f'<rect class="hit" x="0" y="{y0 + i * row_h}" width="{width}" height="{row_h}"/>')
        out.append(f'<text x="{x0 - 10}" y="{y + bar_h - 4}" text-anchor="end" '
                   f'class="{"f-primary" if tried else "f-muted"}">{escape(slug)}</text>')
        x, segs = sx(0), [(k, p) for (k, _), p in zip(PARTS, parts) if p > 0]
        for n, (k, p) in enumerate(segs):
            w = plot_w * p / 100 - (gap if n < len(segs) - 1 else 0)  # 2px surface gap between segments
            if n == len(segs) - 1:
                out.append(f'<path d="{end_rounded(x, y, w, bar_h)}" class="f-{k}"/>')
            else:
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{bar_h}" class="f-{k}"/>')
            x += w + gap
        verdict_txt = f"{verdict} {ng}/{nj}" if tried else "not tried"
        out.append(f'<text x="{sx(comp) + 8:.1f}" y="{y + bar_h - 4}" class="f-primary">'
                   f'<tspan font-weight="600">{comp:.1f}</tspan><tspan class="f-secondary s" dx="6">{escape(verdict_txt)}'
                   f'</tspan></text></g>')
    out.append(f'<line x1="{sx(0)}" x2="{sx(0)}" y1="{y0 - 4}" y2="{y0 + h}" class="k-axis" stroke-width="1"/>')
    return "".join(out), 26 + h + 24


def history_lines(history, top, y0, width):
    """history: {round: {slug: composite}}; the current top ideas are drawn in ink with end labels, the rest recede."""
    rounds = sorted(history, key=int)
    vals = [v for r in rounds for v in history[r].values()]
    lo, hi = min(vals), max(vals)
    lo, hi = (lo - 2) // 5 * 5, -(-(hi + 2) // 5) * 5
    x0, x1, h = 60, width - 230, 200
    sx = lambda i: x0 + (x1 - x0) * i / max(1, len(rounds) - 1)  # noqa: E731
    sy = lambda v: y0 + h - h * (v - lo) / (hi - lo)  # noqa: E731
    out = []
    for v in range(int(lo), int(hi) + 1, 5):
        out.append(f'<line x1="{x0}" x2="{x1}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" class="k-grid" stroke-width="1"/>'
                   f'<text x="{x0 - 8}" y="{sy(v) + 4:.1f}" text-anchor="end" class="f-muted s">{v}</text>')
    for i, r in enumerate(rounds):
        out.append(f'<text x="{sx(i):.1f}" y="{y0 + h + 18}" text-anchor="middle" class="f-muted s">round {r}</text>')
    slugs = sorted({s for r in rounds for s in history[r]}, key=lambda s: s in top)  # top ideas drawn last (on top)
    labels = []
    for s in slugs:
        pts = [(i, history[r][s]) for i, r in enumerate(rounds) if s in history[r]]
        hot = s in top
        d = " ".join(f"{'M' if n == 0 else 'L'}{sx(i):.1f},{sy(v):.1f}" for n, (i, v) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" class="{"k-primary" if hot else "k-axis"}" stroke-width="{2 if hot else 1.5}" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        for i, v in pts:
            out.append(f'<g class="pt"><title>{escape(f"{s}, round {rounds[i]}: {v:.1f}")}</title>'
                       f'<circle class="hit" cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="9"/>'
                       + (f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="4" class="f-primary k-surface" stroke-width="2"/>'
                          if hot else "") + "</g>")
        if hot:
            labels.append([sy(pts[-1][1]), s, pts[-1][1], sx(pts[-1][0])])
    labels.sort()
    for n in range(1, len(labels)):  # nudge end labels apart instead of letting them collide
        labels[n][0] = max(labels[n][0], labels[n - 1][0] + 15)
    for y, s, v, x in labels:
        out.append(f'<text x="{x + 10:.1f}" y="{y + 4:.1f}" class="f-primary s">{escape(s)} '
                   f'<tspan class="f-secondary">{v:.1f}</tspan></text>')
    return "".join(out), h + 30


def render(path, rows, history=None, width=980):
    top = [r[0] for r in rows[:3]]
    parts = [f'<text x="20" y="30" class="t f-primary">Idea leaderboard</text>'
             f'<text x="20" y="50" class="s f-secondary">Composite 0–100. Tried ideas: 40% rubric + 30% judge panel + '
             f'30% not-guilty share. Not tried (grey names): 50% rubric + 50% judge panel. Hover a bar for its numbers.</text>']
    body, h = bars(rows, 72, width)
    parts.append(body)
    y = 72 + h + 20
    if history and len(history) >= 2:
        parts.append(f'<text x="20" y="{y + 20}" class="t f-primary">Composite by round</text>'
                     f'<text x="20" y="{y + 40}" class="s f-secondary">Current top 3 labelled; every other idea in grey. '
                     f'Scores are drift-corrected, so rounds are comparable.</text>')
        body, h2 = history_lines(history, top, y + 64, width)
        parts.append(body)
        y += 64 + h2 + 10
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{y}" viewBox="0 0 {width} {y}" '
           f'role="img" aria-label="Idea leaderboard chart">{style()}'
           f'<rect width="100%" height="100%" class="f-surface"/>{"".join(parts)}</svg>')
    open(path, "w").write(svg)
