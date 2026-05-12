# Spec: Phase 1 — Triage works (status persistence, score chips, new-since-visit)

**Date:** 2026-05-12
**Project:** Camper_Lifestyle dashboard (`~/Developer/Manual Search Script Run/`)
**Target file path (post-approval):** `docs/superpowers/specs/2026-05-12-triage-works-design.md`

## Context

The Camper_Lifestyle dashboard at https://commanderwi11.github.io/camper-lifestyle/ surfaces 95+ van listings scraped from Wallapop, Milanuncios, and Autoscout24. The dashboard's stated purpose is **triage** — quickly cull bad listings and shortlist good ones — but three gaps make it read-only in practice:

1. **Status changes can't be made.** Each listing has a `status` field (`new` / `watching` / `contacted` / `discarded`) shown as a badge in the card header. The status filter dropdown works, but there is no UI to mutate the status. The field is set once by the scraper and never changes.
2. **No relative scoring.** The Sunlight Cliff Adventure 640 is pinned as a reference card, but nothing else is compared to it. Eyeballing whether a €38k 2018 Ducato is a good deal against the reference requires mental math per row.
3. **Returning to the dashboard hides what's new.** Listings arrive over weeks. There's a "Nuevo" status badge, but it's set by the scraper based on whether the listing has been seen before — not relative to the *user's* last visit. After triaging once, every new listing on the next visit blends in with the rest.

Phase 1 closes these gaps. It is the first of four shippable phases planned for this project (Phase 2: honor promise filters; Phase 3: pipeline resilience; Phase 4: data enrichment). Each phase ships independently.

## Goals

- A user can change a listing's status from the card with one click, and the change persists across reloads and devices.
- A user can see at a glance how a listing compares to the reference on price-per-year, price-per-distance, and annual mileage.
- A user returning to the dashboard immediately sees which listings have appeared since their last visit.

## Non-goals

- Bulk status changes / shift-click range select (deferred).
- Photo modals or detail-page enrichment (Phase 4).
- Cross-source dedupe (Phase 3).
- Editing the score thresholds from the UI (constants in `app.js`; tune by editing code).
- New auth — RLS stays anon-permissive, mirroring `camper_stars` and `camper_hidden`.

## Design

### 1. Status persistence

**Supabase schema** (new table, run once in SQL editor):

```sql
create table if not exists camper_status (
  listing_id text primary key,
  status text not null check (status in ('new','watching','contacted','discarded')),
  updated_at timestamptz default now()
);
alter table camper_status enable row level security;
create policy "anon read"   on camper_status for select to anon using (true);
create policy "anon insert" on camper_status for insert to anon with check (true);
create policy "anon update" on camper_status for update to anon using (true) with check (true);
create policy "anon delete" on camper_status for delete to anon using (true);
```

`listing_id` is PK so upserts replace cleanly. No row implies the scraper-assigned `status` from `listings.json` is current.

**Data flow**:
- `init()` loads all rows into `statusMap: Map<string,string>` (mirrors `starredSet`/`hiddenSet` pattern).
- `renderCard` computes `effectiveStatus = statusMap.get(listing.id) ?? listing.status`. Both the header badge and the action bar's "active" highlight read from this.
- The status filter dropdown filters on `effectiveStatus`, not `listing.status`.

**UI** — bottom-of-card action bar, inserted inside `.card-body` after the comment form:

```html
<div class="action-bar" data-listing-id="${listing.id}">
  <button data-status="new"       class="action-btn ${effectiveStatus==='new'?'active':''}">Nuevo</button>
  <button data-status="watching"  class="action-btn ${effectiveStatus==='watching'?'active':''}">Siguiendo</button>
  <button data-status="contacted" class="action-btn ${effectiveStatus==='contacted'?'active':''}">Contactado</button>
  <button data-status="discarded" class="action-btn ${effectiveStatus==='discarded'?'active':''}">Descartado</button>
</div>
```

- Pinned reference card omits the action bar (same exclusion rule as the hide button).
- Click handler: event-delegated on `#listings-grid` (new `handleStatusChange`). Reads `data-status` from the button and `data-listing-id` from the parent. Upserts with `onConflict: 'listing_id'`. Updates `statusMap` and the local button classes optimistically; reverts on Supabase error with a brief alert.
- Re-renders the full grid only if the status filter is active (changing a card's status while filtered by "Siguiendo" should make the card disappear).

### 2. Three score chips

**Reference baseline** — Sunlight Cliff Adventure 640 new: ~€65,000, 0 km, year 2024. Thresholds are tuned against this and the project's max_price=€55k floor.

**Score functions** in `app.js` (top-of-file constants for tunability):

```js
const CURRENT_YEAR = 2026;

function scorePerYear(listing) {
  if (!listing.price || !listing.year) return null;
  const age = Math.max(1, CURRENT_YEAR - listing.year);
  return Math.round(listing.price / age);
}
function scorePerThousandKm(listing) {
  if (!listing.price || !listing.km) return null;
  return Math.round(listing.price / (listing.km / 1000));
}
function scoreKmPerYear(listing) {
  if (!listing.year || !listing.km) return null;
  const age = Math.max(1, CURRENT_YEAR - listing.year);
  return Math.round(listing.km / age);
}

const SCORE_THRESHOLDS = {
  perYear:        { green: 4000,  amber: 7000  },   // €/año
  perThousandKm:  { green: 400,   amber: 800   },   // €/1000km
  kmPerYear:      { green: 10000, amber: 18000 },   // km/año
};
```

**Color rule:** `<= green → green`, `<= amber → amber`, else `red`. Function `colorFor(value, thresholds)` returns a class name.

**Render** — new row between `.card-meta` and `.comments`, only emitted when at least one chip is computable:

```html
<div class="score-chips">
  ${perYear      !== null ? `<span class="score-chip ${colorFor(perYear, T.perYear)}">${perYear.toLocaleString('es-ES')} €/año</span>` : ''}
  ${perThousandKm!== null ? `<span class="score-chip ${colorFor(perThousandKm, T.perThousandKm)}">${perThousandKm.toLocaleString('es-ES')} €/1000km</span>` : ''}
  ${kmPerYear    !== null ? `<span class="score-chip ${colorFor(kmPerYear, T.kmPerYear)}">${kmPerYear.toLocaleString('es-ES')} km/año</span>` : ''}
</div>
```

Reference card (pinned) skips score chips entirely — `if (listing.pinned) chips = ''`.

Most current Wallapop entries have `year`/`km` populated by the scraper; Milanuncios and Autoscout24 entries often don't. Chips appear progressively as Phase 4 enrichment fills in missing fields. This is intentional — the chip row simply contains fewer (or zero) chips for those rows today.

### 3. "Nuevo desde tu última visita"

**State:** `localStorage.last_visit` = ISO date string (`YYYY-MM-DD`).

**On `init()`** (after listings load, before render):
- Read `localStorage.getItem('last_visit')` → `lastVisit`.
- Compute `newCount = allListings.filter(l => l.added_at && lastVisit && l.added_at > lastVisit).length`.
- Compute `newSet = new Set(...ids matching)`.
- Update toolbar label: `#new-count` shows `${newCount} nuevos desde ${lastVisit}` if `lastVisit` and `newCount > 0`; otherwise empty.
- Write today's date to `localStorage.last_visit` (only if `newCount > 0` — see Edge Cases below).

**Card render:** if `newSet.has(listing.id)`, add a ribbon overlay on `.card-photo-wrapper`:

```html
<span class="new-ribbon">✨ Nuevo</span>
```

Positioned top-center, between the star (top-right) and hide (top-left) buttons.

**Toolbar count + filter:**
- `<span id="new-count" class="new-count">` next to `#last-updated`.
- Clicking `#new-count` toggles a session-only "solo nuevos" filter: adds `if (newOnly) listings = listings.filter(l => newSet.has(l.id))` to `render()`. Not persisted; resets on reload. The clicked label gets an `.active` style while the filter is on.

**Edge cases:**
- No `last_visit` in localStorage (first-ever visit): `newCount = 0`, no ribbons, just set today's timestamp and move on. Avoids 95 ribbons on first load.
- `newCount > 0` and user reloads multiple times the same day: we only update `last_visit` once per session (use sessionStorage flag `last_visit_committed`) so the user can refresh during a triage session without losing the "new" markers mid-flow.
- `added_at` missing on a listing: excluded from `newSet` (won't get a ribbon).

## Files modified

- `~/Developer/Manual Search Script Run/docs/app.js`
  - Add `statusMap`, `newSet`, `newOnly` state.
  - Update `init()`: load `camper_status`, compute new-since.
  - Update `render()`: read `effectiveStatus`, apply `newOnly` filter.
  - Update `renderCard()`: action bar, score chips, new ribbon, status badge reads `effectiveStatus`.
  - Add `handleStatusChange()`, `scorePerYear()`, `scorePerThousandKm()`, `scoreKmPerYear()`, `colorFor()`.
  - Add `last_visit` localStorage logic.
- `~/Developer/Manual Search Script Run/docs/style.css`
  - `.action-bar` (flex row, gap, padding-top, border-top), `.action-btn` (subtle button), `.action-btn.active` (filled per status color, reusing `.badge-*` palettes).
  - `.score-chips` (flex row, gap), `.score-chip` (small chip), `.score-chip.green/.amber/.red` (color variants — green `#15803d`, amber `#a16207`, red `#b91c1c`).
  - `.new-ribbon` (absolute position on `.card-photo-wrapper`, top-center, gold/blue gradient, small).
  - `.new-count` (small text, clickable when count > 0), `.new-count.active` (highlighted while filter on).
- `~/Developer/Manual Search Script Run/docs/index.html`
  - Toolbar `<div class="meta">…</div>` becomes `<div class="meta"><span id="last-updated"></span><span id="new-count"></span></div>`.
- Supabase Family_Plan project: run the `camper_status` SQL once.

## Existing patterns reused

- `camper_stars` and `camper_hidden` loading (`app.js:27-28`, `app.js:51-55`) — `camper_status` mirrors exactly. Map vs Set since values matter.
- Event delegation on `#listings-grid` (`app.js:80-81`) — `handleStatusChange` registered the same way as `handleStarToggle`/`handleHideToggle`.
- Conditional re-render after toggle (`app.js:235-237`) — same approach for status change when filter active.
- Pinned card exclusion (`app.js:128` — hide button gated on `!listing.pinned`) — same gate for action bar and score chips.
- Color palette in `.badge-*` rules (`style.css:177-181`) — reuse for `.action-btn.active` variants.

## Verification

1. Run the `camper_status` SQL in Supabase SQL editor; confirm table + 4 policies exist.
2. Hard-refresh the dashboard. Score chips appear on listings with `year`+`km` (mostly Wallapop entries today); reference card has none.
3. Click "Siguiendo" on a card; badge updates, button highlights. Reload — state persists. Open in private window — state visible there too (anon access).
4. Set status filter to "Siguiendo"; only watched cards visible. Click "Descartado" on one; it disappears from the filtered view in-place (no full reload).
5. Verify a card's effective status comes from Supabase, not `listings.json`: edit a row in Supabase table editor; reload dashboard; badge reflects the manual edit.
6. Clear `localStorage.last_visit` in devtools; reload — no ribbons, no count. Reload again — still no ribbons (timestamp was set silently on first reload, no listings post-date it).
7. Manually set `localStorage.last_visit` to a date 7 days ago; reload — ribbons on every listing with `added_at` more recent. Toolbar shows "N nuevos desde YYYY-MM-DD". Click the count → grid filters to those N cards. Click again → unfilters.
8. Reload during a triage session: `last_visit` does NOT update until next browser session (sessionStorage `last_visit_committed` guard). Ribbons stay visible across the working session.
9. Pinned reference card: no action bar, no hide button, no score chips, no new ribbon — only the star is interactive.
10. Mobile width (375px): action bar wraps to 2 rows if needed; score chips wrap below meta; new ribbon doesn't overlap star.
11. Supabase error case: temporarily revoke the `insert` policy, click a status button — alert fires, button reverts to previous state.

## Spec self-review

- **Placeholders:** none. All thresholds, constants, file paths concrete.
- **Internal consistency:** status filter reads `effectiveStatus` everywhere; new-ribbon edge cases match the verification steps.
- **Scope:** single phase, single spec. No coupling to Phase 2/3/4.
- **Ambiguity:** "Nuevo" status vs "Nuevo desde última visita" — disambiguated in spec (former is the listing's persisted state, latter is a visit-relative marker; orthogonal).
