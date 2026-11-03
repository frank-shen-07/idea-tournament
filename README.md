# idea-tournament

A [Claude Code](https://claude.com/claude-code) skill that runs a tournament between hackathon (or product) ideas until the best one wins.

Every idea is scored blind by fresh scorers (a strict rubric and a simulated judge panel), with anchor cards to catch rating drift; the leaders are put on trial in front of a jury of Claudes; weak ideas are revised or replaced; and a leaderboard and chart track the result.

## Requirements

| What | Used for | Install |
|---|---|---|
| `hackathon-idea-evaluator` skill | Rubric score /60 | `npx skillfish add hameed0342j/svh hackathon-idea-evaluator` |
| `agents-data-ai` plugin (`hackathon-ai-strategist` agent) | Judge panel and new challenger ideas | `/plugin marketplace add davepoon/buildwithclaude` then `/plugin install agents-data-ai@buildwithclaude` |

Optional: Python 3 with matplotlib for the score chart.

## Install

Pick one.

**Claude Code plugin** (recommended, easy to update):

```
/plugin marketplace add frank-shen-07/idea-tournament
/plugin install idea-tournament@idea-tournament
```

**skillfish:**

```bash
npx skillfish add frank-shen-07/idea-tournament --all
```

(`--all` installs both skills: `idea-tournament` and the bundled `court`.)

**Manual:** copy both `skills/idea-tournament/` and `skills/court/` into `~/.claude/skills/`.

Then in Claude Code, ask something like: *"Use idea-tournament to evaluate our hackathon ideas in ideas.pdf against the brief in hackathon.pdf."*

## What's inside

- `skills/idea-tournament/SKILL.md`: the process (context file → idea cards → scoring → court trials → leaderboard → revise and repeat)
- `skills/idea-tournament/scripts/blind.py`: anonymises cards (no names, versions or history; word cap)
- `skills/idea-tournament/scripts/scores.py`: median of 3 fresh scorers, anchor-based drift correction
- `skills/idea-tournament/scripts/pairwise.py`: blind head-to-heads in both orders; a revision must win to replace the leader
- `skills/idea-tournament/scripts/pack.py` / `record.py`: one packed input file per agent and saving its JSON reply (keeps each agent to one read + one reply)
- `agents/idea-judge.md`: a Read-only Sonnet agent for scoring and head-to-heads (installed with the plugin)
- `skills/idea-tournament/scripts/leaderboard.py`: builds `LEADERBOARD.md` and `scores.png` from `scores.json`
- `skills/idea-tournament/scripts/advance.sh`: drives several court trials at once

## Bundled: court skill

The `court` skill (prosecutor, defense, jury, judge) is included unmodified from
[alexyc9381/court-skill](https://github.com/alexyc9381/court-skill) by Alex Chen, under its MIT License
(`skills/court/LICENSE`). Thanks to its author.

## License

MIT (this repo's own files). The bundled `skills/court` keeps its own MIT License.
