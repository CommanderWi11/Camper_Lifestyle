# Camper Life-style

**Purpose:** Find the best integral/perfilada motorhome in the Canary Islands for a
family of four with two toddlers. Every Monday at 07:00 the pipeline searches, does
deep research, and publishes the week's **Top 5** to the dashboard.

## Where things live (read this first)

- **The code is HERE:** `~/Developer/Manual Search Script Run/`
- **GitHub Pages serves `docs/` from `main`** (legacy mode, no Actions workflow).
  Pushing to `main` publishes the site: https://commanderwi11.github.io/Camper_Lifestyle/
- The copy under `AI Coworking/01_Personal_HQ/Projects/Assets_HQ/Camper_Lifestyle/`
  is a **dead clone** — an orphaned 3-commit branch from the 2026-05-19 force-push
  incident. Do not plan or edit against it.

## The weekly pipeline

    scripts/harvest.py        Stage A  scrape every source        -> scripts/candidates.json
    scripts/research-prompt.md Stage B  claude -p reads ads, web-searches, ranks
                                        -> scripts/winners.json
    scripts/apply_winners.py  Stage C  validate + fold into board -> docs/listings.json
    git push                  Stage D  Pages redeploys in ~60s

    scripts/weekly-search.sh            orchestrates all four
    launchd/com.openbob.camper-weekly.plist   Mondays 07:00

**Run it now** (any time — it is idempotent per ISO week):

```bash
launchctl kickstart -k gui/$(id -u)/com.openbob.camper-weekly
tail -f ~/Library/Logs/camper-weekly.log
```

To force a re-run of a week that already published, delete its marker in `.state/`.

## Things that will bite you

- **GitHub Actions cannot run this.** The listing sites block datacenter IPs. The old
  `.github/workflows/weekly-search.yml` had a Monday cron and never once produced a
  listing. It is deleted. The job runs on the Mac, on purpose.
- **`claude -p` needs `--append-system-prompt`** with the headless override in
  `weekly-search.sh`. Without it the global CLAUDE.md startup protocol makes a headless
  run reply *"which workstation are we in today?"* instead of doing the work.
- **Never send `Accept-Encoding: br`** from the scrapers. `requests` cannot decode
  Brotli without the optional package, and you get binary garbage that every parser
  fails on *silently*.
- **`docs/listings.json` is a BOARD, not a feed.** Each entry is a past or present
  winner carrying the week it last won. Do not append to it — that is what
  `candidates.json` is for.
- **Supabase is currently dead** (project deleted; see `docs/supabase-setup.sql`). The
  dashboard falls back to localStorage and the weekly search reads
  `scripts/blocklist.json`, so nothing is broken — it just doesn't sync across devices.

## The rubric

Family of four, two toddlers. Hard gates: **≥4 seatbelted travel seats with 3-point
belts** (the spec that silently disqualifies most cheap perfiladas — toddler car seats
need them), ≥4 berths, bathroom with shower, ≤3,500 kg (B licence), Canary Islands,
integral or perfilada. Then scored on family fit (40% — fixed beds and rear bunks are
everything; a bed you rebuild nightly around sleeping toddlers is a serious defect),
value (35%), condition/risk (15% — damp is the #1 killer of used motorhomes), and
Canary practicality (10% — ≤7 m for the roads and ferries).

Full rubric: `scripts/research-prompt.md`.

## Discarding

The 🗑 button on a card means **never show me this again, and never search for it
again** — `harvest.py` reads the discard list before it scrapes. From the terminal:

```bash
./scripts/discard.py <listing-id>       # discard
./scripts/discard.py --undo <listing-id>
./scripts/discard.py --list
```
