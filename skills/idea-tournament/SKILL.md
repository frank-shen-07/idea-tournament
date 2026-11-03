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

## Budget (ask once at the start; default: lean)

A general-purpose sub-agent that opens files one by one costs roughly 30–40k tokens, mostly fixed start-up
overhead resent on every step. Packed files plus the `idea-judge` agent (step 3) cut that to one read and one reply: measured at about 9k
tokens per head-to-head and 22k per scorer (11 cards), so a lean round (3 scorers + 4 head-to-heads) is about 100k.
The number of agents still drives cost. Ask the user which budget to use, and which model sub-agents should run on (the Agent tool's
`model` setting; `sonnet` is a good default for scorers and jurors, `haiku` is cheapest but noisier).

| Setting | Scoring round | Head-to-head (per pair) | Court trial | Retrial for close calls |
|---|---|---|---|---|
| **minimal** | 1 combined scorer (rubric + judge panel in one pass) | done by the scorer, both orders | `--jury 3` | no |
| **lean** (default) | 3 combined scorers | 2 agents: one per order | `--quick` (6 jurors) | only if the margin is 1 vote |
| **full** | 3 rubric + 3 judge-panel scorers | 6 agents: 3 judges × both orders | `--quick` | margin ≤ 2 votes or composites within 5 |

A combined scorer writes both `rubric-<x>.json` and `judges-<x>.json` from one reading of the cards. Use **full**
only for the final decision between the last two or three ideas. Tell the user the agent count before each round.

## Workspace

Create `idea-lab/` in the project:

```
idea-lab/
  context.md            # the shared brief every agent reads (step 1)
  ideas/<slug>.card.md  # one idea per card (step 2)
  ideas/<slug>.case.md  # card + context.md, the file the court reads
  blind/round<N>/       # anonymised cards + key.json for each scoring round (step 3)
  scores/round<N>/      # one JSON file per fresh scorer
  scores.json           # combined, drift-corrected numbers (step 3) + court results (step 4)
  pairwise/<name>/      # blind head-to-heads (step 6)
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

## Step 3: score blind, with fresh scorers and anchors

AI scorers drift upward over rounds and favour whatever is labelled as the newer, longer version. Every
scoring round therefore follows these controls (see "Bias controls" below for why).

1. **Pick 2–3 anchor cards** at the start (e.g. the user's original ideas) and include them in every round,
   unchanged. They measure drift.
2. **Blind the cards:**
   `python3 <skill base directory>/scripts/blind.py idea-lab <N> <slug>... --anchors <anchor-slug>...`
   This strips names, version history and trial talk, assigns random IDs and enforces a word cap (default 450;
   shorten any card it rejects, never raise the cap for one idea). Scorers see only `idea-lab/blind/round<N>/<ID>.md`
   and `context.md`, never `key.json`, the ideas folder, earlier scores or the leaderboard.
3. **Fresh scorers every round** (how many depends on the budget). Spawn new agents each round; never reuse or
   message old ones. Keep each agent to one read and one reply, because every extra step resends its whole context:
   - Pack the round: `python3 <skill base directory>/scripts/pack.py score idea-lab <N>` writes one file with the
     task, rules, rubric, context and every blind card (`blind/round<N>/packed-score.md`).
   - Launch each scorer as the plugin's `idea-judge` agent (Read-only, Sonnet, short instructions) with just the
     packed file's path as the prompt. If that agent type is not available (plugin not installed or not yet
     reloaded), use `general-purpose` with `model: sonnet` and the prompt "Read <path> once (it is your whole task)
     and reply with only the JSON it asks for. Use no other tools and open no other files."
   - Each scorer replies with `{"rubric": {...}, "judges": {...}}`. Save it with
     `python3 <skill base directory>/scripts/record.py score idea-lab <N> <letter>` (reply on stdin).
   The packed file already states the scoring rules: theoretical quality; every data field in the context counts
   as available; no deductions for illustrative numbers; the rubric's other anti-inflation rules; ignore length,
   polish and self-assessment.
4. **Combine:** `python3 <skill base directory>/scripts/scores.py idea-lab <N> rubric` (and `judges`). It takes the
   median of the scorers, records the spread, measures anchor drift against the anchors' first scores and
   subtracts it, then updates `scores.json`.
5. **Noise rule:** a difference smaller than the larger of the two ideas' spreads (or 2 rubric points / 1 judge
   point if spreads are zero) is a tie. Say "tie", not "better".

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
- Build the case file from the **blinded card** (`blind/round<N>/<ID>.md` + `context.md`) so the jury does not see
  version history either.

**Retrial for close calls.** One jury of six is noisy: 5–1 versus 6–0 is a single juror. Run a second trial with a
different `--seed` when the verdict margin is 2 votes or less, or when two ideas you must choose between are within
5 composite points. Add the second jury's votes to the first (`not_guilty` out of `jurors: 12` in `scores.json`)
and use the combined verdict.

## Step 5: the leaderboard

`scores.py` keeps `scores.json` (you add the court fields):

```json
{"slug": {"rubric": 45, "judges": 26, "not_guilty": 5, "jurors": 6, "verdict": "NOT GUILTY", "family": "rent-rebuttal"},
 "untried-slug": {"rubric": 46, "judges": 24, "not_guilty": null, "verdict": "not tried"}}
```

Then run `python3 <skill base directory>/scripts/leaderboard.py idea-lab` → writes `LEADERBOARD.md` and `scores.png`.

Composite (0–100):
- Tried: 40% × rubric/60 + 30% × judges/30 + 30% × not-guilty share.
- Not tried: 50% × rubric/60 + 50% × judges/30 (about what a 4–2 acquittal would give; say so when reporting).

## Step 6: improve and repeat

**Exploration rule (every round).** Polishing one idea family converges on a local optimum: the best version of
one idea, not the best idea. So every round must include:
- **At least 3 brand-new ideas** that do not share a core with anything already on the board (different user,
  decision or technique, not a reframing). Ask `hackathon-ai-strategist` for them, giving it the list of every
  idea family tried so far and asking for ideas outside those families.
- **A cap of 2 consecutive revisions per family.** Track each card's family (e.g. `family: rent-rebuttal` in
  `scores.json`). After two revision rounds in a row on one family, the next round must score new challengers
  before that family can be revised again.
- New ideas are scored blind in the same pass as everything else, so on lean/minimal budgets they add cards, not
  agents. The best new idea of each round goes to trial if it lands in the top 3.

Report how many families are on the board and whether the top 3 are all from one family; if they are, say so.

Each round, also pick from:
1. **Revise** a leader using its judge's "Conditions for acquittal" → new card `rN-<slug>-v2`, score, trial.
2. **Challengers:** ask `hackathon-ai-strategist` for 4 new ideas aimed at the rubric's weak dimensions, giving it
   the leader's card, the scorer's "what would raise it" notes and the list of ideas already tried.
3. **Combine** two strong ideas that share an engine (the evaluator skill's Combination Strategy).
4. **Trial** the top untried ideas.

**Replacing a leader needs a blind head-to-head win, not just a higher score.** A revision is not automatically an
improvement. For any challenger, especially a revision of the leader:

```bash
python3 <skill base directory>/scripts/pairwise.py setup idea-lab <name> <leader-slug> <challenger-slug> --judges <1 lean, 3 full>
```

Each brief is self-contained (context and both blind cards inside). Launch one fresh `idea-judge` agent per
printed brief (judges × both orders), or the `general-purpose` fallback above, and save each reply with
`python3 <skill base directory>/scripts/record.py pair idea-lab <name> <judge> <order>`. Each judge sees two anonymous cards and picks
one; a judge whose pick flips when the order flips counts as a tie. Then run `pairwise.py tally idea-lab <name>`.
The challenger replaces the leader only if it wins a strict majority of judges **and** does not lose on the
composite. Otherwise the leader stays, and the revision is kept only as a note of what was tried. Prune when the user asks (common requests:
drop guilty ideas, drop untried ideas, keep files only for the top 3). Deletions in an untracked folder are
permanent: say so.

## Bias controls (why steps 3–6 look like this)

| Risk | Control |
|---|---|
| Scores creep up round after round | Fresh scorers each round + anchor cards; drift is measured and subtracted |
| "Newer version must be better" | Blind cards: no names, versions or history; head-to-head wins required to replace a leader |
| Longer, more detailed cards win | Same word cap for every card; scorers told to ignore length and polish |
| One scorer's mood | Median of 3 scorers; spread recorded; small differences called ties |
| Polishing one idea family forever | 3 new unrelated ideas per round; max 2 consecutive revisions per family |
| Position bias in comparisons | Every head-to-head is run in both orders; order-flipping judges count as ties |
| One noisy jury | Second trial with a different jury seed for close calls; votes combined |

## Reporting

Keep updates short. At the end, give the user:
- the top 3–4 with rubric, judges, verdict and composite, plus spreads and anchor drift; call ties ties;
- the winner's judge's conditions for acquittal (the to-do list before the event);
- what was replaced, and any place your process had a flaw (e.g. a context file that was missing data);
- file locations.

Never inflate or soften a verdict. If scores plateau (revisions stall within ±2 rubric points), say so and say
what kind of change, not rewording, would move them.
