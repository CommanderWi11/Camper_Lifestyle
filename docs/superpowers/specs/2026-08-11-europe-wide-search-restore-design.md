# Design: Restore Europe-wide search scope

**Date:** 2026-08-11
**Status:** Approved by Luis, pending implementation plan

## Context

The automated daily pipeline (`weekly-search.sh` → harvest.py → `claude -p`
research → `apply_winners.py`/`board.py` → GitHub Pages) was refocused to
Canary-Islands-only scope on 2026-07-30, at Luis's explicit request, reverting
a brief 2026-07-26 Europe-wide rebuild. Since then Luis has continued to find
motorhomes outside the Canary Islands by hand — a periodic manual research
pass, pasted in and ingested via `scripts/ingest_manual_shortlist.py` into the
separate `docs/history.json` view (see project `MEMORY.md`, 2026-07-31 entry).

Session on 2026-08-11: Luis asked to improve the project generally. Discussion
converged on: the automated board's real weak point right now is recall — the
Canary Islands market is genuinely thin (~35-45 units across the whole
archipelago per prior research), and the actual fix is to widen the net back
to Europe, not to add more Canary-specific sources.

**Also found and fixed during this session, unrelated to this design:** the
`com.openbob.motorhome-search-daily` launchd job was not loaded at all
(`launchctl list` didn't show it), and the pipeline log's last entry was
2026-08-08 03:00 — a run that failed on a Claude session limit. No automated
run had published in 3+ days. Reloaded via `launchctl bootstrap`; confirmed
active. This is an operational fix, not part of the scope below, but is the
reason the daily board may look stale as of session start.

## Goal

Restore Europe-wide search scope for the automated daily pipeline, replacing
the Canary-only board entirely (not running alongside it), while keeping
every non-geography-specific improvement made since the 2026-07-26 rebuild.

## Decisions (confirmed with Luis)

- **Board structure:** Replace — one unified Europe-wide Top 5 + Favorites
  board, not a second board or section alongside the Canary one.
- **Manual shortlist workflow:** Keep as backup. Even with automated Europe
  coverage, Stage B's live search may still miss sites outside its portal
  list or need deeper human digging on a specific listing. No change to
  `scripts/ingest_manual_shortlist.py` or `docs/history.json`.
- **Logistics/distance scoring:** No penalty. Matches the original
  2026-07-26 brief — buy anywhere in Europe, self-drive it back, ferry only
  the Canary leg. Do not add distance or shipping-cost weighting.
- **Implementation method:** Port forward, don't revert. Edit the current
  (2026-07-30-refocused) codebase forward, swapping only the
  geography-defining pieces back to European. Do not `git revert` the
  2026-07-30 commit — that would risk losing fixes layered on top of it
  since (discard defense-in-depth, fingerprint tweaks, hang mitigation, the
  "search new stock too" instruction).

## What changes

### Stage A — `scripts/harvest.py`, `scripts/params.json`

- `fetch_milanuncios` / `fetch_coches_net` URLs revert from Canarias-filtered
  back to nationwide Spain:
  - `milanuncios.com/autocaravanas-de-segunda-mano/` (no `/canarias.htm` suffix)
  - `coches.net/autocaravanas-y-remolques/` (no `/canarias/` suffix)
  - These exact URLs were verified live once during the 07-30 change
    (recovered from `git show b0ae4e6`). Re-verify live via `curl` before
    wiring them in — 12 days old, don't trust without a fresh check.
- `params.json`: no changes. Already has no age/price hard-gates (dropped
  2026-07-26, correctly never reinstated).
- No new scraped sources added. Wallapop and the other sources dropped in the
  2026-07-26 "third correction" (non-brief sources) stay dropped — that
  decision wasn't about geography, it was about matching the brief's actual
  portal list, and still applies to the restored Europe-wide brief.

### Stage B — `scripts/research-prompt.md`, `Resources/`, `weekly-search.sh`

- `weekly-search.sh` copies `Resources/europe-motorhome-selling-sites.md`
  into the Stage B scratch dir instead of
  `Resources/canary-motorhome-selling-sites.md`.
- Mark `canary-motorhome-selling-sites.md` superseded-in-place (same pattern
  already used on the Europe file when it was superseded 2026-07-30) — don't
  delete it.
- `research-prompt.md`: restore Europe-wide geography/logistics language
  (buy anywhere in Europe, self-drive + Canary ferry leg only, IVA/IGIC
  import note replaces the local-IGIC-only note). Keep unchanged: every hard
  gate (MAM ≤3,500 kg, length ≥6.90 m, twin beds + infill kit, LHD, ≥4
  belted seats), the no-invented-scoring / no-body-type-filter rules, the
  €50k-100k budget, and the "search new stock too, don't just wait for it"
  instruction added 2026-07-30 — none of these are geography-specific.
- Fetch budget stays as-is (~25-30 fetches, priority-list-then-country-order
  from the portal file). Not widening it in this change.

### Board model, schedule

No changes. `board.py` Top5+Favorites model, single 03:00 `StartCalendarInterval`,
the non-iCloud Stage B scratch dir, and the discard/blocklist
defense-in-depth (both the id-check and the `same_vehicle` relist check) all
stay exactly as they are — none of this was Canary-specific.

### Docs

Update `CLAUDE.md`, `README.md`, and `MEMORY.md` for consistency, matching
the pattern of every prior geography change in this project's history.

### Repo hygiene (found during this session)

Two untracked iCloud conflict-copy files exist: `docs/history 2.json` and
`scripts/ingest_manual_shortlist 2.py`. Before implementation: diff each
against its non-numbered counterpart to check for divergence, then confirm
with Luis before deleting (per standing rule: never delete without asking).

## Explicitly out of scope

- **Wider Stage B fetch budget** (searching more deeply per portal per run).
  Deferred — tune only if a week of real Europe-wide output still shows thin
  recall.
- **Dedicated scrapers for more sources** (mobile.de, AutoScout24, etc.).
  Bigger, ongoing engineering lift (anti-bot handling, selector maintenance —
  see Wallapop's already-bit-rotted scraper). Already an open backlog item;
  not part of this change.
- **Distance/shipping-cost-based scoring.** Explicitly declined by Luis.

## Validation plan

1. Run the full test suite (`tests/`) after the `harvest.py` URL changes — no
   test hardcodes scrape URLs, so no regressions expected, but confirm.
2. Delete today's `.state/<date>.done` marker and run the full pipeline
   end-to-end (Stage A→D) to confirm it actually harvests, researches, and
   publishes Europe-wide (new+used) results under the restored prompt/sources
   before calling this done.
3. Spot-check the published board and dashboard render correctly.
