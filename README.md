# idea-tournament

A [Claude Code](https://claude.com/claude-code) skill that runs a tournament between hackathon (or product) ideas until the best one wins.

Every idea is scored by a strict rubric and a simulated judge panel; the leaders are put on trial in front of a jury of Claudes; weak ideas are revised or replaced; and a leaderboard and chart track the result.

## Requirements

| What | Used for | Install |
|---|---|---|
| `court` skill | Adversarial trial: prosecutor, defense, jury, judge | Clone https://github.com/alexyc9381/court-skill into `~/.claude/skills/court` |
| `hackathon-idea-evaluator` skill | Rubric score /60 | `npx skillfish add hameed0342j/svh hackathon-idea-evaluator` |
| `agents-data-ai` plugin (`hackathon-ai-strategist` agent) | Judge panel and new challenger ideas | `/plugin marketplace add davepoon/buildwithclaude` then `/plugin install agents-data-ai@buildwithclaude` |

Optional: Python 3 with matplotlib for the score chart.

## Install

```bash
git clone https://github.com/frank-shen-07/idea-tournament ~/.claude/skills/idea-tournament
```

Then in Claude Code, ask something like: *"Use idea-tournament to evaluate our hackathon ideas in ideas.pdf against the brief in hackathon.pdf."*

## What's inside

- `SKILL.md`: the process (context file → idea cards → scoring → court trials → leaderboard → revise and repeat)
- `scripts/leaderboard.py`: builds `LEADERBOARD.md` and `scores.png` from `scores.json`
- `scripts/advance.sh`: drives several court trials at once

## License

MIT
