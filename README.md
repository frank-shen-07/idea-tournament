# idea-tournament

A [Claude Code](https://claude.com/claude-code) skill that runs a tournament between hackathon (or product) ideas until the best one wins.

Each round writes new ideas, scores every idea blind with fresh scorers (a rubric and a simulated judge panel) and anchor cards to catch rating drift; the leaders are put on trial in front of a jury of Claudes; weak ideas are revised or replaced; and a leaderboard and chart track the result.

## Requirements

Nothing else to install: the rubric, the court (trial) engine and the three sub-agents are bundled.
Python 3 is required, nothing else.

## Install

Pick one.

**Claude Code plugin** (recommended, easy to update):

```
/plugin marketplace add frank-shen-07/idea-tournament
/plugin install idea-tournament@idea-tournament
```

**skillfish:**

```bash
npx skillfish add frank-shen-07/idea-tournament idea-tournament
```

(skillfish installs the skill only; the three lightweight agents come with the plugin install. Without them the skill falls back to general-purpose agents, which cost about 2–3× more tokens.)

**Manual:** copy `skills/idea-tournament/` into `~/.claude/skills/` and `agents/*.md` into `~/.claude/agents/`.

Then in Claude Code, ask something like: *"Use idea-tournament to evaluate our hackathon ideas in ideas.pdf against the brief in hackathon.pdf."*

## What's inside

- `skills/idea-tournament/SKILL.md`: the round-by-round process, budgets and bias controls
- `skills/idea-tournament/rubric.md`: the /60 rubric with calibration rules
- `skills/idea-tournament/court/`: the bundled trial engine (prosecutor, defense, jury, judge)
- `skills/idea-tournament/scripts/round.py`: runs a whole round in one command (ideas, blind scoring, head-to-heads, trials, leaderboard and chart) and prints a short summary with the cost per step and model
- `skills/idea-tournament/scripts/`: `blind.py` (anonymise cards), `pack.py` (one input file per agent), `record.py` (save replies), `scores.py` (median + drift correction), `pairwise.py` (blind head-to-heads), `advance.sh` (drive trials), `leaderboard.py` + `chart.py` (table and an SVG chart after every round: stacked score bars per idea, plus each idea's score by round)
- `skills/idea-tournament/scripts/run_jobs.py`: runs any job (ideas, scoring, head-to-heads, whole court trials) on any OpenRouter model, e.g. GLM, with exact token and cost logging
- `agents/`: `idea-writer`, `idea-judge`, `court-runner`: lightweight Sonnet sub-agents (one read, one write or reply)

## Cheap models via OpenRouter

Any role can run on an OpenRouter model instead of Claude. Save your key once, in your own terminal:

```bash
python3 ~/.claude/skills/idea-tournament/scripts/openrouter_key.py      # or the path where the skill is installed
```

It asks for the key at a hidden prompt (nothing shows while you paste), checks it with OpenRouter, and saves it
readable only by you. `--check` shows whether it works and how much credit is left; `--remove` deletes it.
Never paste the key into a Claude chat. Then tell Claude which model to use, e.g. *"run the court and idea
writing on openrouter:z-ai/glm-5.3-flash"*. Your brief and ideas are sent to OpenRouter and that model's provider.

## Credits

The trial engine is bundled from [alexyc9381/court-skill](https://github.com/alexyc9381/court-skill) by Alex Chen,
and `idea-writer` is adapted from `hackathon-ai-strategist` in [davepoon/buildwithclaude](https://github.com/davepoon/buildwithclaude).
Both are MIT-licensed; see `THIRD_PARTY.md`.

## License

MIT. Bundled third-party components keep their own MIT licenses (see `THIRD_PARTY.md`).
