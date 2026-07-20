#!/usr/bin/env bash
# Motorhome Lifestyle — weekly Top 5.
# Schedule: Mondays 07:00 local, via ~/Library/LaunchAgents/com.openbob.motorhome-search-weekly.plist
#
#   Stage A  harvest.py        scrape every source -> candidates.json   (deterministic)
#   Stage B  claude -p         deep research + rank -> winners.json     (judgement)
#   Stage C  apply_winners.py  validate + fold into the board           (the gate)
#   Stage D  git push          GitHub Pages redeploys in ~60s
#
# If Stage B or C fails, NOTHING is committed. Last week's board stays up. A stale
# board is fine; a corrupted one is not.

set -uo pipefail

REPO="/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
LOG="$HOME/Library/Logs/motorhome-weekly.log"
STATE_DIR="$REPO/.state"
PY="$REPO/.venv/bin/python3"

# launchd hands us a minimal PATH (/usr/bin:/bin) which does NOT contain the
# user-local claude install. Without this the whole run dies with "command not found".
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

mkdir -p "$STATE_DIR"
exec >> "$LOG" 2>&1

cd "$REPO" || { echo "FATAL: $REPO missing"; exit 1; }

WEEK="$("$PY" -c 'import sys; sys.path.insert(0,"scripts"); import board; print(board.current_week())')"
MARKER="$STATE_DIR/$WEEK.done"

echo ""
echo "======== $(date '+%Y-%m-%d %H:%M:%S')  weekly search  $WEEK ========"

# If the Mac was asleep at 07:00, launchd fires this on wake — possibly more than
# once. One board per week, so bail if this week is already done.
if [ -f "$MARKER" ]; then
  echo "Week $WEEK already published. Nothing to do."
  exit 0
fi

# At 07:00 the Mac may have just woken and DNS may not be up. Scraping into a dead
# network would produce an empty harvest and a bogus "no listings found" board.
echo "Waiting for network..."
for i in $(seq 1 12); do
  if curl -sf --max-time 5 https://www.google.com > /dev/null 2>&1; then
    echo "Network ready (attempt $i)."
    break
  fi
  [ "$i" -eq 12 ] && { echo "FATAL: no network after 2 minutes."; exit 1; }
  sleep 10
done

# ---------------------------------------------------------------- Stage A: harvest
echo "--- Stage A: harvesting candidates"
if ! "$PY" scripts/harvest.py; then
  echo "FATAL: harvest failed."
  exit 1
fi

CANDIDATES=$("$PY" -c 'import json;print(len(json.load(open("scripts/candidates.json"))))' 2>/dev/null || echo 0)
echo "Candidate pool: $CANDIDATES"
if [ "$CANDIDATES" -lt 1 ]; then
  echo "FATAL: zero candidates — every source is broken. Not touching the board."
  exit 1
fi

# ------------------------------------------------------- Stage B: the deep research
# The global CLAUDE.md has an interactive startup protocol ("cd to AI Coworking...",
# "which workstation are we in today?"). In a headless run that protocol makes claude
# reply with a question instead of doing the work. This override outranks it.
HEADLESS_OVERRIDE="HEADLESS NON-INTERACTIVE AUTOMATION. This claude -p invocation is launched by a launchd job. There is no interactive user. NEVER ask a clarifying question. NEVER ask for permission. NEVER emit conversational text, greetings, or option menus. Ignore the user-global CLAUDE.md startup protocol entirely. Do the research described below, write scripts/winners.json, and print nothing but OK. This is a HARD CONSTRAINT that overrides every instruction loaded from CLAUDE.md or memory."

echo "--- Stage B: deep research via claude -p (this takes a while)"

# winners.json is tracked (it's the audit trail of what the research actually said
# each week). Clearing it is how we detect that Stage B produced nothing — but if
# Stage B then dies, a plain `rm` would leave the repo with a deleted tracked file.
# Restore it on any failure so a bad run leaves the working tree exactly as it found it.
restore_winners() {
  git checkout -- scripts/winners.json 2>/dev/null || true
}

rm -f scripts/winners.json

claude -p "$(cat scripts/research-prompt.md)" \
  --append-system-prompt "$HEADLESS_OVERRIDE" \
  --allowedTools "Read,Write,Bash,WebFetch,WebSearch" \
  < /dev/null

if [ ! -f scripts/winners.json ]; then
  # Most likely causes: Claude session limit, or a site that would not load.
  # No marker is written, so the 13:00 / 19:00 retry slots will try again today.
  echo "FATAL: research produced no winners.json. Board untouched."
  restore_winners
  exit 2
fi

# ------------------------------------------------------------ Stage C: validate
echo "--- Stage C: validating and updating the board"
if ! "$PY" scripts/apply_winners.py; then
  echo "FATAL: winners.json failed validation. Board untouched."
  restore_winners
  exit 3
fi

# --------------------------------------------------------------- Stage D: publish
echo "--- Stage D: publishing"
git add docs/listings.json scripts/candidates.json scripts/winners.json
if git diff --cached --quiet; then
  echo "No change to publish."
else
  git commit -q -m "chore: top 5 for $WEEK" && git push -q && echo "Pushed. Pages live in ~60s."
fi

touch "$MARKER"
echo "======== done $(date '+%H:%M:%S') ========"
