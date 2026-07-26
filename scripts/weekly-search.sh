#!/usr/bin/env bash
# Motorhome Lifestyle — refreshes the current week's Top 5, daily.
# Schedule: every day 07:00/13:00/19:00 local, via
# ~/Library/LaunchAgents/com.openbob.motorhome-search-daily.plist
#
#   Stage A  harvest.py        scrape every source -> candidates.json   (deterministic)
#   Stage B  claude -p         deep research + rank -> winners.json     (judgement)
#   Stage C  apply_winners.py  validate + fold into the board           (the gate)
#   Stage D  git push          GitHub Pages redeploys in ~60s
#
# If Stage B or C fails, NOTHING is committed. Last week's board stays up. A stale
# board is fine; a corrupted one is not.
#
# The board is Top 5 (today) + Favorites (starred) — no week-by-week archive. Winners
# that don't repeat and aren't starred simply drop off; a day with nothing new
# re-picks the same winners, and Stage D's `git diff --cached --quiet` check means
# that publishes no new commit — a quiet day is a no-op, not noise. 2026-07-21:
# switched from Monday-only to daily at Luis's request; see MEMORY.md.

set -uo pipefail

REPO="/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
LOG="$HOME/Library/Logs/motorhome-daily.log"
STATE_DIR="$REPO/.state"
PY="$REPO/.venv/bin/python3"

# launchd hands us a minimal PATH (/usr/bin:/bin) which does NOT contain the
# user-local claude install. Without this the whole run dies with "command not found".
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

mkdir -p "$STATE_DIR"
exec >> "$LOG" 2>&1

cd "$REPO" || { echo "FATAL: $REPO missing"; exit 1; }

TODAY="$(date '+%Y-%m-%d')"
MARKER="$STATE_DIR/$TODAY.done"

echo ""
echo "======== $(date '+%Y-%m-%d %H:%M:%S')  daily search ========"

# If the Mac was asleep at 07:00, launchd fires this on wake — possibly more than
# once. One publish per CALENDAR DAY, so bail if today is already done; 13:00/19:00
# are same-day retries if the 07:00 attempt failed (session limit, flaky site, no
# network on wake — none of which are code bugs, all of which happened for real).
if [ -f "$MARKER" ]; then
  echo "$TODAY already published. Nothing to do."
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

# 2026-07-20 through 2026-07-26: Stage B hung on 7 consecutive scheduled runs, every
# hang-sample showing the identical stack (getcwd() stuck in open$NOCANCEL at process
# startup, 0% CPU afterwards, no session transcript ever created). A live interactive
# `claude -p "OK"` from this same iCloud cwd does NOT reproduce it on demand (returns
# in ~5s), so the trigger is specific to the cold/unattended launchd context (minimal
# PATH/env, no TTY, straight after sleep/wake) rather than a blanket "this cwd always
# hangs" fact. Root cause is still not 100% certain, but the fix is cheap and safe
# either way: run Stage B's `claude -p` itself from a small LOCAL non-iCloud scratch
# directory, so iCloud/FileProvider is out of the picture for the one process that's
# actually been shown hanging. Stage A/C/D keep running from the iCloud repo path
# exactly as before — they've never hung.
STAGE_B_SCRATCH="$HOME/Library/Application Support/motorhome-search/stage-b-scratch"
rm -rf "$STAGE_B_SCRATCH"
mkdir -p "$STAGE_B_SCRATCH/scripts"
cp scripts/candidates.json "$STAGE_B_SCRATCH/scripts/candidates.json"

# macOS has no `timeout`/`gtimeout` binary installed, so this is a plain-bash
# watchdog: bound Stage B to STAGE_B_TIMEOUT seconds and kill it on expiry,
# degrading a hang to the same "no winners.json" path as a real failure below —
# which the existing 13:00/19:00 retry slots already recover from unattended.
STAGE_B_TIMEOUT=1500  # 25 min; re-tune once real Europe-wide runs show actual wall-clock time
STAGE_B_START=$(date +%s)

# `exec` replaces this subshell with the claude process itself (no extra process
# layer), so $! below is the real claude PID — `sample`/`kill` target it directly.
( cd "$STAGE_B_SCRATCH" && exec claude -p "$(cat "$REPO/scripts/research-prompt.md")" \
  --append-system-prompt "$HEADLESS_OVERRIDE" \
  --allowedTools "Read,Write,Bash,WebFetch,WebSearch" \
  < /dev/null ) &
CLAUDE_PID=$!

while kill -0 "$CLAUDE_PID" 2>/dev/null; do
  if [ $(( $(date +%s) - STAGE_B_START )) -ge "$STAGE_B_TIMEOUT" ]; then
    echo "FATAL: claude -p exceeded ${STAGE_B_TIMEOUT}s — killing as a hang, not real work."
    # `sample` suspends the process and dumps every thread's call stack — it needs no
    # sudo for a same-user process — so grab that evidence BEFORE killing. Now that
    # Stage B runs from a local scratch dir (see above), a fresh hang-sample here
    # would tell us whether the scratch-dir fix actually helped or the cause lies
    # elsewhere (e.g. a genuinely slow/hostile portal, now that Stage B fetches many
    # more of them) — read it, don't assume.
    HANG_SAMPLE="$STATE_DIR/hang-sample-$(date '+%Y-%m-%d_%H%M%S').txt"
    sample "$CLAUDE_PID" 5 -file "$HANG_SAMPLE" 2>&1 | tail -3
    echo "Hung process call stacks captured to $HANG_SAMPLE — inspect before assuming the cause."
    kill -TERM "$CLAUDE_PID" 2>/dev/null
    sleep 5
    kill -KILL "$CLAUDE_PID" 2>/dev/null
    break
  fi
  sleep 10
done
wait "$CLAUDE_PID" 2>/dev/null
echo "Stage B took $(( $(date +%s) - STAGE_B_START ))s."

# Bring the output back from the scratch dir into the repo. Leave the scratch dir
# itself in place (not cleaned up) so a hang's partial state is inspectable afterward.
if [ -f "$STAGE_B_SCRATCH/scripts/winners.json" ]; then
  cp "$STAGE_B_SCRATCH/scripts/winners.json" scripts/winners.json
fi

if [ ! -f scripts/winners.json ]; then
  # Most likely causes: Claude session limit, a hang (see watchdog above), or a site
  # that would not load. No marker is written, so the 13:00 / 19:00 retry slots will
  # try again today.
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
git add docs/listings.json scripts/candidates.json scripts/winners.json scripts/starred.json
if git diff --cached --quiet; then
  echo "No change to publish."
else
  git commit -q -m "chore: top 5 refresh $TODAY" && git push -q && echo "Pushed. Pages live in ~60s."
fi

touch "$MARKER"
echo "======== done $(date '+%H:%M:%S') ========"
