---
name: idea-tournament
description: Run a tournament between hackathon (or product) ideas until the best one wins. Writes new ideas, scores every idea blind with a rubric and a simulated judge panel, puts the leaders on trial in front of a jury, revises or replaces the weak ones, and keeps a leaderboard and chart, all on a fixed token budget. Use when the user wants to pick, stress-test or improve ideas for a hackathon, pitch or competition, says "evaluate our ideas", "which idea should we build", "keep iterating until something beats this", or asks for an idea leaderboard.
---

# Idea Tournament

You run a loop: **write → score blind → head-to-head → trial → leaderboard**, round after round, until the
leaderboard settles or the budget runs out. You are the organiser: you never write ideas, score, argue or vote
yourself; sub-agents do that. Everything needed is bundled in this plugin:

| Bundled | What it does |
|---|---|
| `rubric.md` | The /60 rubric (Novelty, Feasibility, Scalability, Impact, Demo-ability, Domain fit) with calibration rules |
| `court/` | Trial engine: prosecutor, defense, jury, judge (`court.py`, from alexyc9381/court-skill, MIT; instructions in `court/COURT.md`) |
| `scripts/` | `round.py` (a whole round in one command), `run_jobs.py` (job runner: Claude via `claude -p`, or OpenRouter), `blind.py`, `pack.py`, `record.py`, `scores.py`, `pairwise.py`, `advance.sh`, `leaderboard.py` |
| Agents `idea-writer`, `idea-judge`, `court-runner` | Lightweight Sonnet sub-agents with minimal tools: they read one file and write or reply, so each costs a fraction of a general-purpose agent |

Below, `SKILL` means this skill's base directory (Claude Code prints it when the skill loads). Python 3 is
required; nothing else (the chart is plain SVG). If an agent type above is missing (plugin not installed or not
reloaded), use `general-purpose` with `model: sonnet` and the prompt "Read <path> once (it is your whole task) and
do only what it says. Open no other files unless it tells you to."

## Start: ask once, then run on autopilot

Ask the user these in one message, with defaults, then run rounds without further questions:
1. **Budget:** minimal / **lean** (default) / full (table below), and how many rounds or a token cap.
2. **Provider and model** for sub-agent jobs, per role (ideas / scoring / head-to-heads / court) or for all:
   - **claude** (default): the bundled agents on `sonnet` (or haiku, cheapest but noisier).
   - **openrouter:<model>**, e.g. `openrouter:z-ai/glm-5.3-flash`: jobs run through `scripts/run_jobs.py` instead
     of sub-agents (see "Running jobs on OpenRouter"). Far cheaper, but data goes to OpenRouter and the model's
     provider, and quality must be checked: run one scoring round on both and compare before trusting it.
3. Where the brief and any starting ideas are.

| Setting | New ideas | Scorers | Head-to-head per pair | Trial | Retrial | ≈ tokens per round* |
|---|---|---|---|---|---|---|
| **minimal** | 3 | 1 | scorer does it | `--jury 3` | no | ~45k + trials |
| **lean** | 3 | 3 | 2 (one per order) | `--quick` (6) | margin of 1 vote | ~110k + trials |
| **full** | 3 | 3 + 3 separate | 6 (3 judges × 2 orders) | `--quick` | margin ≤ 2 or composites within 5 | ~200k + trials |

*Measured with the lightweight agents: ~9k per head-to-head, ~22k per scorer (11 cards, grows ~2k per 3 cards),
idea writing ~10–15k. A trial is 11 `court-runner` jobs. Before each round, tell the user the agent count and
estimate; after it, report what it used.

Token rules that apply everywhere: one packed input file per agent; agents write their output to files and reply
one word, so you never read or retype their output; never reuse or
message an old agent; launch independent agents in one message; keep your own updates to a line or two.

## Run each round with one command (default)

Your own turns are the most expensive part of a round: each one re-reads the whole conversation. So after step 1
and the starting cards, run every round as ONE background command and read only its summary:

```bash
python3 SKILL/scripts/round.py idea-lab <N> [--ideas claude:sonnet] [--score claude:sonnet] \
    [--pairs z-ai/glm-5.3-flash] [--court z-ai/glm-5.3-flash] [--new 3] [--scorers 3] [--max-trials 2]
```

It does steps A to E below with no sub-agents: Claude jobs run through `claude -p` (no tools, one call each),
OpenRouter jobs through the API. Every reply is checked (JSON, every blind ID scored, juror `VOTE:` line, card
format and the 450-word cap counted exactly) and retried; exact tokens and cost go to `usage-round<N>.jsonl`. It
prints the top 5, what happened (new ideas, head-to-heads, trials, drift) and the cost per step and model, in about
20 lines. Report those lines; do not open the job files. Start the next round only after reading the summary.
Use the step-by-step agent flow below only to debug a step. Trial rule in `round.py`: every untried idea in the
top 3 (up to `--max-trials`), so no top-3 idea is ranked on an assumed verdict.

## Running jobs on OpenRouter

Every job is a self-contained brief, so any model can run it. `run_jobs.py` pastes in every file a brief names,
asks the model for each output file the brief names, writes them, checks the format (JSON, juror `VOTE:` line,
card header), retries once, skips jobs already done, and logs exact tokens and cost to `openrouter-usage.jsonl`.

```bash
R="python3 SKILL/scripts/run_jobs.py --model <openrouter-model> --log idea-lab/openrouter-usage.jsonl"
$R idea-lab/ideas/packed-ideas-round<N>.md                                      # step A: new ideas
$R idea-lab/blind/round<N>/packed-score.md:a ...:b ...:c idea-lab/pairwise/<name>/brief-*.md   # steps B and C
$R --court idea-lab/trials <slug>...                                            # step D: whole trials, start to finish
```

Wherever a step below says "launch an agent", use the matching command instead; everything else is the same.
The key comes from `OPENROUTER_API_KEY` or `~/.config/openrouter/key`; never ask the user to paste it into chat.
Use `--dry-run` to see each job's inputs, outputs and prompt size without calling the API.

## Workspace

```
idea-lab/
  context.md              # the shared brief (step 1)
  ideas/<slug>.card.md    # one idea per card (step 2)
  blind/round<N>/         # anonymised cards, key.json, packed-score.md
  scores/round<N>/        # one JSON per scorer
  scores.json             # combined, drift-corrected scores + court results + family
  pairwise/<name>/        # blind head-to-heads
  trials/<slug>/.court/   # court trials
  LEADERBOARD.md, scores.svg   # table + chart; the chart is embedded in LEADERBOARD.md
```

## Step 1: the context file (get this right first)

Sub-agents see only what you give them. Write `context.md` from the user's brief:
- The event: date, length, venue, who competes (including AI teams).
- **The judging criteria, verbatim.**
- **Every data source / API field the brief lists, verbatim.** Copy the full list. A missing field makes juries
  convict ideas for "data that doesn't exist" when it does.
- What the brief suggests building (others will build those) and the team's constraints.

Show the user a 5-line summary and confirm before round 1. If verdicts later cite missing data the brief provides,
fix `context.md` and re-run those trials.

## Step 2: idea cards

Every card uses the same format and a 450-word cap (the starting ideas too):

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

Record each card's `family` (its core idea) in `scores.json`. Pick 2–3 **anchor** cards (e.g. the user's starting
ideas) that never change; they go into every scoring round to measure drift.

## One round

**A. New ideas (1 agent).** Exploration rule: every round adds **at least 3 brand-new ideas** whose core differs
from every family on the board. A family may be revised at most **2 rounds in a row**; then it must wait a round.
```bash
python3 SKILL/scripts/pack.py ideas idea-lab <N> 3 [--revise <leader-slug> --notes <notes-file>]
```
Launch one `idea-writer` with the printed path as its prompt. Notes for a revision: the leader's judge's
"Conditions for acquittal" and scorers' weak dimensions. It writes `ideas/n<N>-<i>.card.md` (and
`<leader>-rev<N>.card.md`); rename them to readable slugs and set their family.

**B. Score blind (1 or 3 agents).**
```bash
python3 SKILL/scripts/blind.py idea-lab <N> <slug>... --anchors <anchor>...   # random IDs, no names/history, word cap
python3 SKILL/scripts/pack.py score idea-lab <N>                              # one file: task, rubric, context, cards
```
Launch the scorers (`idea-judge`, prompt = `<path of blind/round<N>/packed-score.md> <letter a|b|c>`) in one
message, **together with step C's head-to-head judges**. Each writes `scores/round<N>/reply-<letter>.json` (never
paste replies yourself; that spends your own tokens). Split each with
`python3 SKILL/scripts/record.py score idea-lab <N> <letter> < idea-lab/scores/round<N>/reply-<letter>.json`, then:
```bash
python3 SKILL/scripts/scores.py idea-lab <N> rubric && python3 SKILL/scripts/scores.py idea-lab <N> judges
```
`scores.py` takes the median, records the spread, and subtracts anchor drift. **Noise rule:** a gap smaller than
the larger spread of the two ideas (minimum 2 rubric / 1 judge point) is a tie; say "tie".

**C. Head-to-head (2 or 6 agents per pair).** A challenger (any revision, or a new idea that outscores the leader)
replaces the leader only by winning a blind head-to-head, not by a higher score alone:
```bash
python3 SKILL/scripts/pairwise.py setup idea-lab <name> <leader> <challenger> --judges <1 lean | 3 full>
```
Launch one `idea-judge` per printed brief (it writes its own result file), then
`pairwise.py tally idea-lab <name>`. Each judge sees both orders; a pick that flips with the order is a tie.
The challenger wins only with a strict majority **and** no lower composite.

**D. Trials (11 agents each).** Trial the round's best new idea if it reaches the top 3, and any idea about to
become the leader. Build the case from the **blinded** card so the jury sees no history:
```bash
mkdir -p idea-lab/trials/<slug>/.court
cat idea-lab/blind/round<N>/<ID>.md <(echo) idea-lab/context.md > idea-lab/trials/<slug>/.court/case.md
cd idea-lab/trials/<slug> && python3 SKILL/court/court.py init --case-file .court/case.md --quick --seed 9
```
Keep `--seed 9` for every trial so juries are comparable. Drive all open trials with
`SKILL/scripts/advance.sh idea-lab/trials <state-file> <slug>...`: it prints every brief that is ready and not yet
launched (and renders finished verdicts). Launch one `court-runner` per brief (prompt = the brief path), at most
~20 at once; re-run `advance.sh` when a batch finishes. Skip the judge phase once a verdict is decided. Follow
`court/COURT.md` for anything else (failed jurors, rendering). **Retrial** with a different seed when the margin
is within the budget's limit; add votes (`not_guilty` out of `jurors: 12`).

**E. Leaderboard and chart.** Add court results to `scores.json`, then
`python3 SKILL/scripts/leaderboard.py idea-lab --round <N>`. It writes `LEADERBOARD.md` and `scores.svg`: stacked
bars per idea (rubric, judge panel, court share), the score and verdict at each bar's end, untried ideas in grey,
and from round 2 on a composite-by-round line chart with the current top 3 labelled (`--round` records the
history). Hover a bar or point in a browser for its numbers. After every round, give the user the chart's path
so they can open it.
Composite (0–100): tried = 40% rubric/60 + 30% judges/30 + 30% not-guilty share; not tried = 50/50 rubric and
judges (about a 4–2 acquittal; say so). Report in a few lines: top 3, ties, anchor drift, families on the board
(warn if the top 3 share one family), tokens used.

Stop when the round budget is reached, or when two rounds pass with no change in the top 3.

## Bias controls (why the round looks like this)

| Risk | Control |
|---|---|
| Scores creep up round after round | Fresh scorers each round + anchor cards; drift is measured and subtracted |
| "Newer version must be better" | Blind cards (no names, versions, history); head-to-head win required to replace a leader |
| Longer, more polished cards win | Same 450-word cap; scorers told to ignore length and polish |
| One scorer's mood | Median of 3; spread recorded; small gaps called ties |
| Polishing one family forever | 3 new unrelated ideas every round; max 2 consecutive revisions per family |
| Position bias | Every head-to-head in both orders; order-flipping picks are ties |
| One noisy jury | Retrial with a new seed for close calls; votes combined |

Scoring rules (already inside every packed file): judge theoretical quality as if built as described; every data
field in the context counts as available; no deductions for illustrative numbers; apply the rubric's calibration
rules; ignore length, polish and self-assessment.

## Reporting

At the end give: the top 3–4 (rubric, judges, verdict, composite, spreads); the winner's judge's "Conditions for
acquittal" as a to-do list; what was replaced; any flaw in your own process (say it plainly); file locations;
total tokens. Never inflate or soften a verdict. If scores plateau, say what kind of change, not rewording, would
move them. Pruning (dropping guilty or untried ideas, deleting files) only when the user asks; deletions in an
untracked folder are permanent, so say so.
