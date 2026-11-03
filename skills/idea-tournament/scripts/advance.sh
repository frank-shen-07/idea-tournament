#!/bin/bash
# Drive several court trials at once.
# Prints every brief that is ready to launch and has not been printed before; renders finished verdicts.
# Usage: advance.sh <trials-dir> <state-file> <slug> [<slug>...]
set -u
T=$1; STATE=$2; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
C="${COURT_PY:-$HERE/../court/court.py}"
[ -f "$C" ] || C="$HOME/.claude/skills/court/court.py"
touch "$STATE"
for s in "$@"; do
  cd "$T/$s" || continue
  n=$(python3 -I "$C" next)
  if echo "$n" | grep -q "trial is over"; then
    [ -f "$(cat .court/LATEST)/VERDICT.md" ] || { python3 -I "$C" render >/dev/null; echo "DONE $s"; }
    continue
  fi
  p=$(echo "$n" | grep -o 'prompts [a-z]*' | cut -d' ' -f2)
  [ -n "$p" ] || continue
  for b in $(python3 -I "$C" prompts "$p" | grep -o 'brief=.*' | cut -d= -f2); do
    grep -qx "$b" "$STATE" || { echo "$b"; echo "$b" >> "$STATE"; }
  done
done
