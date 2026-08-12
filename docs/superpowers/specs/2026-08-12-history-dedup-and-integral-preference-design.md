# Design: History view dedup + integral-vs-perfilada preference

**Date:** 2026-08-12
**Status:** Approved by Luis, pending implementation plan

## Context

Session on 2026-08-12, right after the 2026-08-11 Europe-wide search restore went
live: Luis asked for two changes to the Motorhome_Search project.

1. "No caravan should be repeated. Only the latest find should be on the dashboard,
   old ones removed so as not to have duplicates."
2. "Favour integral caravans from now on, but don't let a good perfilada deal pass.
   Add that to search."

Investigation before designing: the automated Top5+Favorites board (`board.py`)
already dedupes correctly today — `update_board()` promotes a repeat winner in
place via `same_vehicle()`, never duplicating it. The actual duplicate problem
lives in the separate **History view** (`docs/history.json`, Luis's periodic
manual-shortlist pastes, rendered as one dated sub-section per batch below
Top5/Favoritos). Because that view renders every dated snapshot independently
with no cross-date dedup, a vehicle that's held over unchanged across many pasted
reports currently gets a separate card on every date it's mentioned. Measured on
the live data: 7 distinct listing ids repeat across 3–13 dates each (one Dethleffs
listing — `2dehands_be-f9438584` — appears in 13 separate date sections).

## Decisions (confirmed with Luis)

- **Scope of dedup: History view only.** The automated board already behaves
  correctly; nothing there needs to change.
- **Keep the data, change only what renders.** `docs/history.json` keeps every
  dated mention forever (it's the audit trail used for things like
  cross-referencing a corrupted pasted URL against an earlier date's clean copy —
  see `MEMORY.md`'s 2026-07-27 entry). The dashboard will only ever display each
  vehicle once, under its most recent date.
- **Match by exact id only**, not cross-portal fuzzy matching. Essentially all of
  today's real duplicates are the same id (same URL) reappearing across dates —
  exact-id dedup covers the actual problem with zero false-positive risk. Reusing
  `harvest.py`'s `same_vehicle()` fuzzy title matching was considered and rejected:
  that logic is tuned for the automated harvester's SEO-stuffed titles, not Luis's
  own annotated shortlist titles (e.g. "#1 Etrusco T 7400 SBC — sin cambios"), and
  applying it here risks false merges with no real upside given how few (if any)
  cross-portal dupes exist in the manual data today.
- **Integral preference is prompt-only** — a change to `scripts/research-prompt.md`
  (Stage B's ranking judgment), not a UI badge on dashboard cards.
- **Integral preference is a soft tiebreaker, not a filter.** The project has an
  explicit, deliberate "no body-type restriction" rule (no vehicle is excluded or
  penalized for being a capuchina, camper van, integral, or perfilada — see
  `CLAUDE.md`'s rubric section and the 2026-07-26 rebuild history in `MEMORY.md`).
  This change does not reopen that decision. It adds a preference that only
  matters when comparing otherwise-similar candidates; a perfilada that's a clear
  standout deal is exactly as valid a winner as before.

## What changes

### 1. History view dedup — `docs/app.js` only

No changes to `docs/history.json`, `scripts/ingest_manual_shortlist.py`, or
`board.py`/`apply_winners.py`. `historySnapshots` is already sorted newest-first
(`scripts/ingest_manual_shortlist.py`'s `sorted(..., reverse=True)` when writing
the file) — the fix relies on that existing order.

`renderHistory()` currently loops every snapshot and renders every entry not
starred/hidden, with no memory across iterations. Change: track a `seenIds`
`Set`, seeded with every id already shown in Top 5 + Favoritos (via the existing
`known`/`top5Ids`/`starredSet` values already computed in `render()`) so a
vehicle already on the main board doesn't also get a stale History card. Then,
walking snapshots newest→oldest (already the iteration order): for each date,
render only entries whose id is not yet in `seenIds`; after rendering a date's
surviving entries, add their ids to `seenIds` before moving to the next (older)
date.

Net effect: each vehicle's card appears exactly once on the page, under its most
recent date section. Older mentions of the same id are silently skipped in
rendering — the underlying JSON is untouched. A date whose entries are now *all*
duplicates of a more recent date disappears from the page entirely (the existing
`if (!entries.length) continue` skip-empty-date behavior now also triggers from
dedup, not just from starring/hiding).

### 2. Integral-vs-perfilada preference — `scripts/research-prompt.md`

Two touch points in the existing brief text:

- **New bullet in "Preferencias fuertes"**, placed immediately after the existing
  bathroom-separated preference bullet, matching that bullet's tone (a real
  preference with an explicit "don't over-apply this" carve-out):

  > **Carrocería integral (Clase A) preferida sobre perfilada** — a igualdad del
  > resto (precio, estado, distribución, kilometraje), prefiere un integral. Esto
  > no es un filtro: una perfilada que sea claramente un buen chollo (precio muy
  > por debajo de mercado, estado excelente, cumple todo lo demás) no debe
  > descartarse ni penalizarse solo por su carrocería — sigue siendo un candidato
  > tan válido como antes. Capuchinas y camper vans no ganan ni pierden puntos por
  > este criterio; es una preferencia integral-vs-perfilada específicamente.

- **Add it to the ranking-comparison list** in the "Cómo ordenar" section. That
  section currently instructs Stage B to compare each candidate against "camas
  gemelas + kit, baño separado, 4ª/5ª plaza, historial de mantenimiento y sin
  humedad, IVA/tipo de vendedor" — insert "tipo de carrocería (integral
  preferido)" into that list so the preference is actually applied during
  ranking, not just stated once and forgotten.

### 3. Docs consistency — `CLAUDE.md`

Append a clarifying clause to the rubric section's existing "No body-type
restriction" sentence, so it's clear the hard rule (no exclusion) and the new
soft preference (integral favored as a tiebreaker) coexist without
contradiction. Current sentence:

> **No body-type restriction** — carried over from the 2026-07-26 rebuild, still
> correct: don't exclude capuchinas/campervans or require integral/perfilada.

New sentence:

> **No body-type restriction** — carried over from the 2026-07-26 rebuild, still
> correct: don't exclude capuchinas/campervans or require integral/perfilada.
> (2026-08-12: added a soft tiebreaker on top — Stage B now favors integral over
> perfilada when candidates are otherwise comparable, but this is a preference,
> not a filter; a standout perfilada deal wins exactly as before. See
> `research-prompt.md`.)

## Explicitly out of scope

- Any change to `docs/history.json`'s stored data or `ingest_manual_shortlist.py`.
- Any change to the automated Top5+Favorites board or `board.py` — it already
  dedupes correctly.
- A dashboard-visible integral/perfilada badge or tag.
- Cross-portal fuzzy same-vehicle matching in the History view.
- Any change to the hard gates or the "no body-type restriction" rule itself.

## Validation plan

1. Unit-level: a small, focused test (or manual JSON-driven check, since
   `app.js` has no existing test harness in this project — confirm this at
   planning time) verifying that given a synthetic `historySnapshots` array with
   a repeated id across two dates, only the newer date's card renders.
2. Manual/visual: load the live dashboard (or a local copy) and confirm a
   currently-repeating id (e.g. `2dehands_be-f9438584`) now shows exactly once,
   under its most recent date, and that its older date sections either show
   correctly-reduced entries or disappear if they had no other unique listings.
3. For the integral preference: no code test applies (it's prompt text for an
   LLM). Validate by re-reading the final `research-prompt.md` for internal
   consistency (the new preference doesn't contradict the "no body-type
   restriction" hard-rule bullet) — a live `claude -p` re-run is not required
   specifically for this change, since the daily 03:00 job will naturally
   exercise it on its next run.
