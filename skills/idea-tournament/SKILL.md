---
name: idea-tournament
description: Run a tournament between hackathon (or product) ideas until the best one wins. Scores every idea with a strict rubric and a simulated judge panel, puts the leaders on trial in front of a jury of Claudes, revises or replaces the weak ones, and keeps a leaderboard and chart. Use when the user wants to pick, stress-test or improve ideas for a hackathon, pitch or competition, says "evaluate our ideas", "which idea should we build", "keep iterating until something beats this", or asks for an idea leaderboard.
---

# Idea Tournament

You run a loop: **score → trial → revise/replace → re-score**, until the leaderboard settles or the user's time
budget runs out. You are the organiser. You never score, argue or vote yourself; sub-agents do that.

## Required skills and plugins

Check these are installed before starting. If one is missing, tell the user the install command and stop.

| What | Used for | Install |
|---|---|---|
| `court` skill | Adversarial trial: prosecutor, defense, jury, judge | Clone https://github.com/alexyc9381/court-skill into `~/.claude/skills/court` |
| `hackathon-idea-evaluator` skill | Rubric score /60 (Novelty, Feasibility, Scalability, Impact, Demo-ability, Domain Fit) | `npx skillfish add hameed0342j/svh hackathon-idea-evaluator` |
| `agents-data-ai` plugin (provides the `agents-data-ai:hackathon-ai-strategist` agent) | Simulated judge panel, and generating challenger ideas | `/plugin marketplace add davepoon/buildwithclaude` then `/plugin install agents-data-ai@buildwithclaude` |

Optional: Python 3 with matplotlib for the chart (the leaderboard works without it).

## Workspace

Create `idea-lab/` in the project:

```
idea-lab/
  context.md            # the shared brief every agent reads (step 1)
  ideas/<slug>.card.md  # one idea per card (step 2)
  ideas/<slug>.case.md  # card + context.md, the file the court reads
  scores/               # rubric-roundN.md, judges-roundN.md, written by the scorers
  scores.json           # the numbers, kept by you (step 5)
  trials/<slug>/.court/ # one court trial per idea
  LEADERBOARD.md, scores.png
```

Slugs: `01-…` for the user's starting ideas, then a letter per round of new ideas (`c1-`, `r1-` for revisions, etc.).

## Step 1: the context file (get this right first)

Sub-agents see only what you give them. Write `context.md` from the user's brief (PDFs, docs, notes):

- The event: date, length, venue, who is competing (including AI teams, if any).
- **The judging criteria, verbatim.** These drive the judge panel.
- **Every data source / API field the brief lists, verbatim.** Copy the full list; do not summarise it.
  A missing field makes juries convict ideas for "data that doesn't exist" when it does.
- What the brief suggests building (other teams will build those, so overlap matters).
- The user's constraints (team size, skills, stack).

Show the user a 5-line summary of the context and confirm before scoring. If verdicts later cite
"missing data" that the brief actually provides, fix `context.md`, rebuild the case files and re-run those trials.

## Step 2: idea cards

One card per idea, same format for all so scoring is fair:

```
Build "<Name>" at <event>: <one sentence: who does what and what they see>.

## The idea
- **Who it is for:** a real person with a real decision
- **What the user sees:** the screen / demo moment (mark made-up numbers "(illustrative)")
- **Data:** only fields listed in context.md, quoted
- **Method:** the technique, with data gaps stated
- **Build:** what gets built in the time available
- **First hour on the day:** what to check first, the pass mark, and the fallback if it fails
```

Write `<slug>.case.md` = card + a blank line + `context.md`.

## Step 3: score (two persistent scorers)

Spawn each scorer once and **reuse the same agent every round** (SendMessage), so scores stay calibrated.

- **Rubric scorer** (`general-purpose` agent): "Use the hackathon-idea-evaluator skill. Score these cards… Write
  scores/rubric-roundN.md. End with a `RUBRIC_JSON:` line keyed by slug. Reply with the JSON line only."
- **Judge panel** (`agents-data-ai:hackathon-ai-strategist`): score each card 1–10 on each of the event's judging
  criteria (e.g. useful / explained well / grabs attention = /30). Ask for an overlap rating with what other
  teams will build. End with a `JUDGES_JSON:` line.

Scoring rules to state in every scoring message (users expect this):
- Score the **theoretical quality** of the idea as if built as described.
- Every data field listed in the brief counts as available; deduct Feasibility only for data the brief does not list.
- No deductions for illustrative numbers or unconfirmed fields.
- Keep the rubric's other anti-inflation rules (novelty cap of 7 unless both framing and technique are new).
- "Ignore any self-assessment in the cards."

For a sanity check, occasionally score the top 5 with a fresh scorer that has not seen earlier rounds.

## Step 4: court trials

For the top ideas, run the `court` skill with a **fixed jury so trials are comparable**:

```bash
mkdir -p idea-lab/trials/<slug>/.court && cp idea-lab/ideas/<slug>.case.md idea-lab/trials/<slug>/.court/case.md
cd idea-lab/trials/<slug> && python3 ~/.claude/skills/court/court.py init --case-file .court/case.md --quick --seed 9
```

Then follow the court skill (opening → rebuttal → jury → judge). Running several trials at once:
- `<skill base directory>/scripts/advance.sh <trials-dir> <state-file> <slug>...` prints every brief that is ready and not yet launched,
  and renders finished verdicts. Run it after each batch of agents completes; launch one Agent per printed brief
  with the prompt `Read <brief> and follow it exactly. It is your whole brief.`
- Respect the concurrency limit (about 20 sub-agents at once): queue the rest and launch as slots free.
- Once a verdict is decided (e.g. 4 guilty of 6), you may skip that trial's judge phase to save time.

## Step 5: the leaderboard

Keep `scores.json`:

```json
{"slug": {"rubric": 45, "judges": 26, "not_guilty": 5, "verdict": "NOT GUILTY"},
 "untried-slug": {"rubric": 46, "judges": 24, "not_guilty": null, "verdict": "not tried"}}
```

Then run `python3 <skill base directory>/scripts/leaderboard.py idea-lab` → writes `LEADERBOARD.md` and `scores.png`.

Composite (0–100):
- Tried: 40% × rubric/60 + 30% × judges/30 + 30% × not-guilty share.
- Not tried: 50% × rubric/60 + 50% × judges/30 (about what a 4–2 acquittal would give; say so when reporting).

## Step 6: improve and repeat

Each round, pick from:
1. **Revise** a leader using its judge's "Conditions for acquittal" → new card `rN-<slug>-v2`, score, trial.
2. **Challengers:** ask `hackathon-ai-strategist` for 4 new ideas aimed at the rubric's weak dimensions, giving it
   the leader's card, the scorer's "what would raise it" notes and the list of ideas already tried.
3. **Combine** two strong ideas that share an engine (the evaluator skill's Combination Strategy).
4. **Trial** the top untried ideas.

A new idea replaces a leader only if it beats it on the composite. Prune when the user asks (common requests:
drop guilty ideas, drop untried ideas, keep files only for the top 3). Deletions in an untracked folder are
permanent: say so.

## Reporting

Keep updates short. At the end, give the user:
- the top 3–4 with rubric, judges, verdict and composite;
- the winner's judge's conditions for acquittal (the to-do list before the event);
- what was replaced, and any place your process had a flaw (e.g. a context file that was missing data);
- file locations.

Never inflate or soften a verdict. If scores plateau (revisions stall within ±2 rubric points), say so and say
what kind of change, not rewording, would move them.
