# History Dedup + Integral Preference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the History view from showing the same caravan across multiple dated sections (keep only its most recent mention), and add a soft integral-over-perfilada ranking preference to the automated Stage B research prompt.

**Architecture:** Two independent, small changes. (1) A new pure, dependency-free JS function (`dedupeHistoryByLatest`) in a new file `docs/history-dedup.js`, loaded via a plain `<script>` tag before `app.js` and wired into `renderHistory()` — `docs/history.json` itself is never modified, only what renders. (2) Two text edits to `scripts/research-prompt.md` (a new preference bullet + one word added to the ranking-comparison list) plus one clarifying sentence in `CLAUDE.md`.

**Tech Stack:** Plain vanilla JS (no build step, no framework — `docs/app.js`/`docs/index.html` are loaded directly by the browser), Node's built-in `node:test` runner for the one new JS test (zero new dependencies — there is no existing JS test harness in this project), Python/pytest for the regression checkpoint, Markdown/Spanish prose for the prompt.

## Global Constraints

- `docs/history.json` and `scripts/ingest_manual_shortlist.py` are **not modified** — every dated mention of every listing stays in the JSON forever. Only what the dashboard *renders* changes.
- Dedup scope is the History view only. The automated Top5+Favorites board (`board.py`) already dedupes correctly (verified: a repeat winner is promoted in place, never duplicated) and must not be touched.
- Dedup matches by **exact listing id only** — no fuzzy/cross-portal matching, no reuse of `harvest.py`'s `same_vehicle()`.
- The integral preference is **prompt-only** (`scripts/research-prompt.md`), not a dashboard UI badge.
- The integral preference is a **soft tiebreaker, not a filter** — it must not contradict or weaken the existing "no body-type restriction" rule (no vehicle excluded or penalized for body type) in either `research-prompt.md` or `CLAUDE.md`. A standout perfilada deal must remain exactly as valid a winner as before.
- No JS build tooling, bundler, or test framework is introduced. The new function must work as a plain global `<script>` in the browser AND be `require()`-able from a Node test with zero dependencies.

---

### Task 1: History view dedup

**Files:**
- Create: `docs/history-dedup.js`
- Create: `tests/test_history_dedup.js`
- Modify: `docs/app.js:97-149` (`render()` and `renderHistory()`)
- Modify: `docs/index.html:24-25` (add a `<script>` tag)

**Interfaces:**
- Produces: `dedupeHistoryByLatest(historySnapshots, excludeIds)` — pure function.
  - `historySnapshots`: array of `{ date: string, entries: Array<{id: string, ...}> }`, already sorted newest-first (this is how `docs/history.json` is written by `scripts/ingest_manual_shortlist.py` — do not re-sort).
  - `excludeIds`: a `Set<string>` (or any iterable) of listing ids to exclude from every snapshot entirely (used for ids already shown in Top 5/Favoritos/hidden).
  - Returns: a NEW array of `{ date, entries }` objects — snapshots with `entries` filtered so each id appears in at most one snapshot (the newest one that mentions it); snapshots left with zero entries are omitted. Does not mutate its inputs.
  - Available in the browser as the global function `dedupeHistoryByLatest` (classic `<script>`, no `type="module"`), and via `require('../docs/history-dedup.js').dedupeHistoryByLatest` from Node.

- [ ] **Step 1: Write the failing test**

Create `tests/test_history_dedup.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { dedupeHistoryByLatest } = require('../docs/history-dedup.js');

test('a repeated id across dates keeps only the newest snapshot copy', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a', title: 'Van A v2' }, { id: 'b', title: 'Van B' }] },
    { date: '2026-08-01', entries: [{ id: 'a', title: 'Van A v1' }, { id: 'c', title: 'Van C' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set());
  assert.equal(result.length, 2);
  assert.deepEqual(result[0].entries.map(e => e.id), ['a', 'b']);
  assert.deepEqual(result[1].entries.map(e => e.id), ['c']);
  assert.equal(result[0].entries[0].title, 'Van A v2');
});

test('excludeIds removes a listing from every date, not just the first', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a' }, { id: 'b' }] },
    { date: '2026-08-01', entries: [{ id: 'a' }, { id: 'c' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set(['a']));
  assert.deepEqual(result[0].entries.map(e => e.id), ['b']);
  assert.deepEqual(result[1].entries.map(e => e.id), ['c']);
});

test('a snapshot left with zero entries after dedup is dropped entirely', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a' }] },
    { date: '2026-08-01', entries: [{ id: 'a' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set());
  assert.equal(result.length, 1);
  assert.equal(result[0].date, '2026-08-03');
});

test('unrelated ids on different dates are all kept, order preserved', () => {
  const snapshots = [
    { date: '2026-08-03', entries: [{ id: 'a' }] },
    { date: '2026-08-01', entries: [{ id: 'b' }] },
  ];
  const result = dedupeHistoryByLatest(snapshots, new Set());
  assert.equal(result.length, 2);
  assert.equal(result[0].date, '2026-08-03');
  assert.equal(result[1].date, '2026-08-01');
});

test('does not mutate the input snapshots array or its entries', () => {
  const original = [
    { date: '2026-08-03', entries: [{ id: 'a' }] },
    { date: '2026-08-01', entries: [{ id: 'a' }] },
  ];
  const before = JSON.parse(JSON.stringify(original));
  dedupeHistoryByLatest(original, new Set());
  assert.deepEqual(original, before);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test tests/test_history_dedup.js`
Expected: FAIL — `Cannot find module '../docs/history-dedup.js'` (the file doesn't exist yet).

- [ ] **Step 3: Write the minimal implementation**

Create `docs/history-dedup.js`:

```js
/** Given history.json's dated snapshots (already sorted newest-first by
 *  scripts/ingest_manual_shortlist.py) and a set of ids to exclude entirely
 *  (already shown elsewhere on the page — Top 5, Favoritos, or hidden), return
 *  the snapshots with entries filtered so each listing id appears in at most
 *  ONE snapshot: the newest one that mentions it. Snapshots left with zero
 *  entries are dropped. Pure — does not mutate historySnapshots or excludeIds.
 *
 *  docs/history.json itself is never touched by this — every dated mention
 *  stays in the file forever, this only decides what the dashboard renders.
 */
function dedupeHistoryByLatest(historySnapshots, excludeIds) {
  const seen = new Set(excludeIds || []);
  const result = [];
  for (const snapshot of historySnapshots) {
    const entries = snapshot.entries.filter(e => !seen.has(e.id));
    for (const e of entries) seen.add(e.id);
    if (entries.length) result.push({ ...snapshot, entries });
  }
  return result;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { dedupeHistoryByLatest };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node --test tests/test_history_dedup.js`
Expected: PASS — 5 tests, 0 failures.

- [ ] **Step 5: Load the new script in the browser before app.js**

In `docs/index.html`, replace:

```html
  <script src="app.js"></script>
```

with:

```html
  <script src="history-dedup.js"></script>
  <script src="app.js"></script>
```

- [ ] **Step 6: Wire the pure function into `renderHistory()` and `render()`**

In `docs/app.js`, replace the `render()` function:

```javascript
function render() {
  const known = allKnownEntries();
  const listings = allListings.filter(l => !hiddenSet.has(l.id));
  const { top5, favorites } = splitTop5AndFavorites(listings, known);
  const grid = document.getElementById('listings-grid');

  if (!top5.length && !favorites.length && !historySnapshots.length) {
    grid.innerHTML = '<p class="msg">Nada por aquí todavía.</p>';
    return;
  }

  let html = '<section><h2>Top 5</h2>';
  html += top5.length
    ? `<div class="grid">${top5.map(renderCard).join('')}</div>`
    : '<p class="msg">Sin ganadores hoy.</p>';
  html += '</section>';

  html += '<section><h2 class="favorites-heading">Favoritos</h2>';
  html += favorites.length
    ? `<div class="grid">${favorites.map(renderCard).join('')}</div>`
    : '<p class="msg">Pulsa ★ en una autocaravana para guardarla aquí.</p>';
  html += '</section>';

  html += renderHistory();

  grid.innerHTML = html;
}
```

with:

```javascript
function render() {
  const known = allKnownEntries();
  const listings = allListings.filter(l => !hiddenSet.has(l.id));
  const { top5, favorites } = splitTop5AndFavorites(listings, known);
  const grid = document.getElementById('listings-grid');

  if (!top5.length && !favorites.length && !historySnapshots.length) {
    grid.innerHTML = '<p class="msg">Nada por aquí todavía.</p>';
    return;
  }

  let html = '<section><h2>Top 5</h2>';
  html += top5.length
    ? `<div class="grid">${top5.map(renderCard).join('')}</div>`
    : '<p class="msg">Sin ganadores hoy.</p>';
  html += '</section>';

  html += '<section><h2 class="favorites-heading">Favoritos</h2>';
  html += favorites.length
    ? `<div class="grid">${favorites.map(renderCard).join('')}</div>`
    : '<p class="msg">Pulsa ★ en una autocaravana para guardarla aquí.</p>';
  html += '</section>';

  const top5Ids = new Set(top5.map(l => l.id));
  html += renderHistory(top5Ids);

  grid.innerHTML = html;
}
```

Then replace `renderHistory()`:

```javascript
/** Manual research snapshots (history.json), one dated sub-section per batch,
 *  all nested under a single "Manual Searches" umbrella section (just below
 *  Favoritos). A listing already shown in Favoritos (starred) or discarded is
 *  skipped here so it isn't shown twice — starring/deleting collapses across
 *  every date that mentions the same listing, since they share the same id. */
function renderHistory() {
  if (!historySnapshots.length) return '';
  let body = '';
  for (const snapshot of historySnapshots) {
    const entries = snapshot.entries.filter(e => !hiddenSet.has(e.id) && !starredSet.has(e.id));
    if (!entries.length) continue;
    body += `<div class="history-batch"><h3 class="history-heading">${formatDateEs(snapshot.date)}</h3>`;
    body += `<div class="grid">${entries.map(renderCard).join('')}</div>`;
    body += '</div>';
  }
  if (!body) return '';
  return `<section><h2 class="manual-heading">Búsquedas manuales</h2>${body}</section>`;
}
```

with:

```javascript
/** Manual research snapshots (history.json), one dated sub-section per batch,
 *  all nested under a single "Manual Searches" umbrella section (just below
 *  Favoritos). A listing already shown in Top 5, Favoritos (starred), or
 *  discarded is excluded here so it isn't shown twice. Across dates, each
 *  vehicle (by id) is shown at most once, under its most recent date — see
 *  dedupeHistoryByLatest in history-dedup.js. docs/history.json itself keeps
 *  every dated mention; only rendering is deduped. */
function renderHistory(top5Ids) {
  if (!historySnapshots.length) return '';
  const excludeIds = new Set([...hiddenSet, ...starredSet, ...top5Ids]);
  const deduped = dedupeHistoryByLatest(historySnapshots, excludeIds);
  if (!deduped.length) return '';
  let body = '';
  for (const snapshot of deduped) {
    body += `<div class="history-batch"><h3 class="history-heading">${formatDateEs(snapshot.date)}</h3>`;
    body += `<div class="grid">${snapshot.entries.map(renderCard).join('')}</div>`;
    body += '</div>';
  }
  return `<section><h2 class="manual-heading">Búsquedas manuales</h2>${body}</section>`;
}
```

- [ ] **Step 7: Run the JS test suite again to confirm nothing regressed**

Run: `node --test tests/test_history_dedup.js`
Expected: PASS — 5 tests, 0 failures (this step is a formality since `docs/app.js` isn't imported by the test, but confirms the repo is in a consistent state before moving on).

- [ ] **Step 8: Run the full Python test suite as a regression checkpoint**

Run: `.venv/bin/python3 -m pytest tests/ -q`
Expected: PASS — same count as before this task (this task touches no Python files, so no count change is expected; run it anyway since `tests/` now also contains `test_history_dedup.js` and pytest must be confirmed to still collect only its own files cleanly, not error out on the new `.js` file).

- [ ] **Step 9: Commit**

```bash
git add docs/history-dedup.js docs/app.js docs/index.html tests/test_history_dedup.js
git commit -m "feat: dedup History view by latest date per listing id"
```

---

### Task 2: Integral-vs-perfilada preference

**Files:**
- Modify: `scripts/research-prompt.md:81-89` (Preferencias fuertes section)
- Modify: `scripts/research-prompt.md:102-111` (Cómo ordenar section)
- Modify: `CLAUDE.md:133-134` (The rubric section)

**Interfaces:** None — pure prose files, no code consumes or produces anything here.

- [ ] **Step 1: Write the verification check (expect it to fail first)**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
grep -c "Carrocería integral (Clase A) preferida" scripts/research-prompt.md   # expect 0
grep -c "tipo de carrocería (integral preferido)" scripts/research-prompt.md  # expect 0
grep -c "favors integral over perfilada" CLAUDE.md                            # expect 0
```

- [ ] **Step 2: Add the new preference bullet to research-prompt.md**

Replace:

```markdown
### Preferencias fuertes (no eliminan, pero pesan mucho)

- **Baño y ducha separados** (WC independiente de la ducha). Un *Raumbad* convertible
  que separe completamente cuenta como separado. Un baño combinado (todo en el mismo
  espacio) es aceptable solo si el resto del trato es excelente — márcalo como
  compromiso en `flags`.
- **4ª y 5ª plaza para los niños** — cama abatible delantera o dinette convertible.
- **Historial de mantenimiento completo, sin antecedentes de humedad.**
- **IVA** — ver "Logística y coste real" más abajo.
```

with:

```markdown
### Preferencias fuertes (no eliminan, pero pesan mucho)

- **Baño y ducha separados** (WC independiente de la ducha). Un *Raumbad* convertible
  que separe completamente cuenta como separado. Un baño combinado (todo en el mismo
  espacio) es aceptable solo si el resto del trato es excelente — márcalo como
  compromiso en `flags`.
- **Carrocería integral (Clase A) preferida sobre perfilada** — a igualdad del resto
  (precio, estado, distribución, kilometraje), prefiere un integral. Esto no es un
  filtro: una perfilada que sea claramente un buen chollo (precio muy por debajo de
  mercado, estado excelente, cumple todo lo demás) no debe descartarse ni penalizarse
  solo por su carrocería — sigue siendo un candidato tan válido como antes. Capuchinas
  y camper vans no ganan ni pierden puntos por este criterio; es una preferencia
  integral-vs-perfilada específicamente.
- **4ª y 5ª plaza para los niños** — cama abatible delantera o dinette convertible.
- **Historial de mantenimiento completo, sin antecedentes de humedad.**
- **IVA** — ver "Logística y coste real" más abajo.
```

- [ ] **Step 3: Add it to the ranking-comparison list**

Replace:

```markdown
Ordena por **valor global** — así lo pide la familia, sin fórmula ni porcentajes
fijos. No hay pesos predefinidos: usa tu juicio, comparando cada candidato contra
las preferencias fuertes y los extras de arriba (camas gemelas + kit, baño separado,
4ª/5ª plaza, historial de mantenimiento y sin humedad, IVA/tipo de vendedor) y contra
lo que ese modelo/año realmente vale en el **mercado europeo real** (no solo en el
país donde está publicado — busca ese mismo modelo/año a la venta en otros países o
en un concesionario nuevo, aplicando la regla de kilometraje de arriba a las
unidades de ocasión). Ningún factor individual manda sobre
los demás — es una valoración de conjunto, igual que pediría la familia si mirara los
anuncios ella misma.
```

with:

```markdown
Ordena por **valor global** — así lo pide la familia, sin fórmula ni porcentajes
fijos. No hay pesos predefinidos: usa tu juicio, comparando cada candidato contra
las preferencias fuertes y los extras de arriba (camas gemelas + kit, baño separado,
tipo de carrocería (integral preferido), 4ª/5ª plaza, historial de mantenimiento y
sin humedad, IVA/tipo de vendedor) y contra lo que ese modelo/año realmente vale en
el **mercado europeo real** (no solo en el país donde está publicado — busca ese
mismo modelo/año a la venta en otros países o en un concesionario nuevo, aplicando
la regla de kilometraje de arriba a las unidades de ocasión). Ningún factor
individual manda sobre los demás — es una valoración de conjunto, igual que pediría
la familia si mirara los anuncios ella misma.
```

- [ ] **Step 4: Sync CLAUDE.md's rubric section**

Replace:

```markdown
**No body-type restriction** — carried over from the 2026-07-26 rebuild, still
correct: don't exclude capuchinas/campervans or require integral/perfilada.
**No invented percentage scoring** — same, "rank by overall value" with no
```

with:

```markdown
**No body-type restriction** — carried over from the 2026-07-26 rebuild, still
correct: don't exclude capuchinas/campervans or require integral/perfilada.
(2026-08-12: added a soft tiebreaker on top — Stage B now favors integral over
perfilada when candidates are otherwise comparable, but this is a preference,
not a filter; a standout perfilada deal wins exactly as before. See
`research-prompt.md`.) **No invented percentage scoring** — same, "rank by overall value" with no
```

- [ ] **Step 5: Run the verification check to confirm it now passes**

```bash
grep -c "Carrocería integral (Clase A) preferida" scripts/research-prompt.md   # expect 1
grep -c "tipo de carrocería (integral preferido)" scripts/research-prompt.md  # expect 1
grep -c "favors integral over perfilada" CLAUDE.md                            # expect 1
```

- [ ] **Step 6: Confirm no contradiction with the hard "no body-type restriction" rule**

```bash
grep -n "no ha pedido excluir ningún tipo" scripts/research-prompt.md
```

Expected: this line still exists unchanged (`"la familia no ha pedido excluir ningún tipo de carrocería..."` in the "Ya NO son requisitos eliminatorios" section) — confirming the hard rule and the new soft preference coexist without one silently overwriting the other. Read both sections by eye to confirm they don't read as contradictory (the hard-gate section says no exclusion; the new preference explicitly says "esto no es un filtro").

- [ ] **Step 7: Run the full test suite as a regression checkpoint**

Run: `.venv/bin/python3 -m pytest tests/ -q`
Expected: PASS — this task touches no Python files, so no regressions expected; confirms the repo is still healthy.

- [ ] **Step 8: Commit**

```bash
git add scripts/research-prompt.md CLAUDE.md
git commit -m "feat: add integral-over-perfilada soft ranking preference"
```

---

### Task 3: Deploy and verify live

**Files:** None modified — this task pushes Tasks 1-2's commits and verifies the result on the live GitHub Pages site.

**Interfaces:** None.

**Context:** `docs/` is served live at https://commanderwi11.github.io/Motorhome_Search/. Task 1's fix only has an observable effect once pushed (the currently-live page still shows the old un-deduped History view). Task 2's prompt change will only visibly affect the board's Top 5 on the next real Stage B run (the daily 03:00 job, or a manual trigger) — this task does NOT force a live pipeline re-run for that; the design's own validation plan explicitly says the daily job will naturally exercise it.

- [ ] **Step 1: Confirm the working tree is clean and both tasks' commits are present**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
git log --oneline -5
git status
```

Expected: the two commits from Task 1 and Task 2 appear at the top of the log; working tree clean (or only pre-existing untracked files like `docs/superpowers/plans/`, `docs/superpowers/specs/` if not yet committed by this point — those are unrelated to this plan and don't block pushing).

- [ ] **Step 2: Push to origin**

```bash
git push origin main
```

Before running this, confirm with Luis that pushing now is fine (this republishes the live dashboard within ~60s) — do not push silently.

- [ ] **Step 3: Verify the new script loads on the live site**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://commanderwi11.github.io/Motorhome_Search/history-dedup.js
```

Expected: `200` (allow ~60-90s after the push for GitHub Pages to redeploy before checking — if it 404s immediately, wait and retry rather than assuming failure).

- [ ] **Step 4: Visually confirm the dedup on the live dashboard**

Per this workspace's global CLAUDE.md rule, use the `playwriter` CLI via Bash (never `mcp__playwriter__execute`). Navigate to https://commanderwi11.github.io/Motorhome_Search/ and confirm:
- The page renders without errors (Top 5, Favoritos, and Búsquedas manuales sections all appear).
- A listing id known to have repeated across many dates before this change — `2dehands_be-f9438584` (previously appeared in 13 separate date sections) — now appears in the rendered page's HTML/DOM exactly once. You can check this via the browser tool's page-content inspection (count occurrences of that id or its associated title/URL in the rendered output) or via `curl -s https://commanderwi11.github.io/Motorhome_Search/history.json | python3 -c "import json,sys; h=json.load(sys.stdin); print(sum(1 for s in h for e in s['entries'] if e['id']=='2dehands_be-f9438584'))"` to confirm the *data* still has all its historical mentions (should print a number >1, proving the JSON is untouched) while the live page shows it only once.

- [ ] **Step 5: Report back to Luis**

Summarize: both commits pushed, the dedup confirmed live (previously-13x-repeating listing now shows once), `docs/history.json` confirmed unchanged (data intact), and note that the integral preference will take effect on the next real Stage B research run (tonight's 03:00 job or a manual trigger, at Luis's discretion — not forced as part of this task).
