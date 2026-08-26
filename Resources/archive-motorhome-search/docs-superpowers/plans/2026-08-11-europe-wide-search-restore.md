# Europe-Wide Search Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore Europe-wide search scope for the automated daily motorhome pipeline, replacing the 2026-07-30 Canary-only board entirely, while keeping every non-geography improvement made since (new+used search, Top5+Favorites model, discard defense-in-depth, hang mitigation).

**Architecture:** Port forward, not `git revert`. Six files change: `scripts/harvest.py` (Stage A scrape URLs), `Resources/*-motorhome-selling-sites.md` (which portal list is active), `scripts/research-prompt.md` (Stage B brief), `scripts/weekly-search.sh` (which portal file Stage B reads), and `CLAUDE.md`/`README.md`/`MEMORY.md` (docs). `params.json`, `board.py`, `apply_winners.py`, `app.js`, and the launchd schedule are untouched — confirmed by grep, no geography-specific content in any of them.

**Tech Stack:** Python 3 (`.venv/bin/python3`), pytest, bash, Markdown/Spanish prose (Stage B prompt).

## Global Constraints

- Board structure: **replace** the Canary board with one unified Europe-wide Top 5 + Favorites board — not a second board or section.
- Manual shortlist workflow (`scripts/ingest_manual_shortlist.py`, `docs/history.json`): **no changes**.
- Logistics/distance scoring: **no penalty** — buy anywhere in Europe, self-drive back, ferry only the Canary leg. Do not add distance/shipping-cost weighting.
- Do **not** `git revert` the 2026-07-30 commit (`fb2abff`) — edit files forward instead, to avoid losing the new+used search addition and other non-geography fixes bundled into that same commit.
- `params.json`: **no changes** (confirmed already geography-neutral).
- Stage B fetch budget: **unchanged** (~25-30 fetches, priority-list-then-country-order). Do not widen it in this change.
- Never delete a file without asking first (standing project rule) — applies to Task 1's iCloud conflict copies.
- All hard gates in `research-prompt.md` stay exactly as worded: MAM ≤3,500 kg, length ≥6.90 m, twin beds + infill kit, LHD, ≥4 belted seats, €50k-100k budget, no-invented-scoring, no-body-type-filter, "search new stock too" instruction.

---

### Task 1: Repo hygiene — remove stale iCloud conflict-copy files

**Files:**
- Delete (pending confirmation): `docs/history 2.json`
- Delete (pending confirmation): `scripts/ingest_manual_shortlist 2.py`

**Interfaces:** None — this is standalone file cleanup, no code depends on it.

**Context:** Two untracked iCloud conflict-copy files exist in the repo (`git status` shows them as `??`). The design spec requires diffing each against its non-numbered counterpart before deleting, then confirming with Luis (per the project's standing "never delete without asking" rule). The diff has already been run once during planning:

```
docs/history.json: 752 lines only in the main file, 0 lines only in the numbered copy
scripts/ingest_manual_shortlist.py: 334 lines only in the main file, 0 lines only in the numbered copy
```

Both numbered copies are exact prefixes of the current files — older, shorter snapshots with zero unique content. Re-verify this hasn't changed (the numbered copies could theoretically have been touched since planning) before deleting.

- [ ] **Step 1: Re-run the divergence diff**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
diff "docs/history 2.json" "docs/history.json" | grep '^<' | wc -l
diff "scripts/ingest_manual_shortlist 2.py" "scripts/ingest_manual_shortlist.py" | grep '^<' | wc -l
```

Expected: both print `0` (no lines exist only in the numbered copy). If either prints a nonzero number, STOP — that means the numbered copy has unique content the main file lacks. Show the diverging lines to Luis before proceeding; do not delete.

- [ ] **Step 2: Confirm with Luis before deleting**

Use AskUserQuestion (or ask directly in conversation): "Both `docs/history 2.json` and `scripts/ingest_manual_shortlist 2.py` are stale iCloud conflict copies — strict subsets of their non-numbered counterparts, zero unique content. OK to delete both?" Do not proceed to Step 3 without an explicit yes.

- [ ] **Step 3: Delete on confirmation**

```bash
git rm -f "docs/history 2.json" "scripts/ingest_manual_shortlist 2.py" 2>/dev/null || rm -f "docs/history 2.json" "scripts/ingest_manual_shortlist 2.py"
git status
```

(They're untracked per the initial `git status`, so plain `rm` is what actually removes them — the `git rm` is a no-op fallback in case they were added since.)

- [ ] **Step 4: Commit** — skip if these were never tracked (nothing to commit for an untracked-file deletion, `git status` should just show them gone from the `??` list).

---

### Task 2: Stage A — restore `harvest.py` scrape URLs to nationwide Spain

**Files:**
- Modify: `scripts/harvest.py:1-20` (module docstring), `scripts/harvest.py:380-394` (`fetch_milanuncios`), `scripts/harvest.py:486-509` (`fetch_coches_net`)
- Test: `tests/test_harvest.py` (append a new test function)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — `fetch_milanuncios(params)` and `fetch_coches_net(params)` keep their existing signatures and return shape (`list[dict]` with `id/title/price/year/km/sleeping/bathroom/location/source/url/photo/status/added_at` keys). Only the literal URL each function requests changes.

**Context:** The two functions currently hit Canarias-filtered URLs (`.../canarias.htm`, `.../canarias/`). These need to revert to the nationwide-Spain URLs they had before the 2026-07-30 refocus. No test today asserts these URL strings — write one first so the geography revert is pinned down, not just hand-verified.

- [ ] **Step 1: Verify both nationwide URLs are still live**

```bash
curl -sS -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" -o /tmp/mila.html -w "milanuncios: HTTP %{http_code}\n" "https://www.milanuncios.com/autocaravanas-de-segunda-mano/"
grep -qi "algo no va bien" /tmp/mila.html && echo "BOT BLOCK" || echo "milanuncios: no bot-block stub"

curl -sS -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" -o /tmp/coches.html -w "coches.net: HTTP %{http_code}\n" "https://www.coches.net/autocaravanas-y-remolques/"
grep -qi "algo no va bien" /tmp/coches.html && echo "BOT BLOCK" || echo "coches.net: no bot-block stub"
```

Expected: both `HTTP 200`, both "no bot-block stub". (Already confirmed once during planning — this step re-confirms at execution time since the design spec explicitly says not to trust a check older than same-day.) If either fails, STOP and report to Luis before touching `harvest.py` — do not guess a replacement URL.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_harvest.py`:

```python
def test_scrape_urls_are_nationwide_spain_not_canarias_filtered():
    """2026-08-11: scope restored to Europe-wide; Stage A's two deterministic
    scrapers cover nationwide Spain again, not the Canarias-filtered URLs from
    the 2026-07-30 detour."""
    import inspect
    mila_src = inspect.getsource(harvest.fetch_milanuncios)
    coches_src = inspect.getsource(harvest.fetch_coches_net)
    assert "canarias.htm" not in mila_src
    assert "https://www.milanuncios.com/autocaravanas-de-segunda-mano/\"" in mila_src
    assert "/canarias/" not in coches_src
    assert "https://www.coches.net/autocaravanas-y-remolques/?page=1\"" in coches_src
```

Check the top of `tests/test_harvest.py` already does `import harvest` (or equivalent) — if it imports differently (e.g. `from scripts import harvest`), match that existing import style instead of adding a duplicate import.

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
.venv/bin/python3 -m pytest tests/test_harvest.py::test_scrape_urls_are_nationwide_spain_not_canarias_filtered -v
```

Expected: FAIL — `canarias.htm` is still present in `fetch_milanuncios`'s source.

- [ ] **Step 3: Edit the module docstring**

In `scripts/harvest.py`, replace:

```python
"""Stage A of the daily pipeline: harvest Canary Islands motorhome candidates.

This script is deliberately DUMB. It casts a wide net and writes every plausible
candidate it finds to candidates.json — no body-type filtering, no age filtering,
no price filtering. It does not rank, score, or pick winners — that is Stage B
(`claude -p`, driven by research-prompt.md), which reads the detail pages and
judges every candidate against the family's actual brief.

2026-07-30: refocused to the Canary Islands only (used + new), reverting the
2026-07-26 Europe-wide detour. Milanuncios and Coches.net are scraped here with
their Canarias-filtered URLs (not nationwide Spain) — deterministic Stage A
coverage. Everything else — Wallapop, Autocasion, AutoScout24 Spain, known local
dealers (RentCamper Canarias, Autocaravanas Canarias), and live search for new
(0km) dealer stock — has no deterministic scraper and is Stage B's job via live
WebSearch/WebFetch, per `Resources/canary-motorhome-selling-sites.md`.

Discarded listings (the 🗑 button -> Supabase `camper_hidden`) are excluded here,
so a discard means "never searched again", not merely "hidden in the UI".
"""
```

with:

```python
"""Stage A of the daily pipeline: harvest Europe-wide motorhome candidates.

This script is deliberately DUMB. It casts a wide net and writes every plausible
candidate it finds to candidates.json — no body-type filtering, no age filtering,
no price filtering. It does not rank, score, or pick winners — that is Stage B
(`claude -p`, driven by research-prompt.md), which reads the detail pages and
judges every candidate against the family's actual brief.

2026-08-11: restored Europe-wide scope (used + new), reverting the 2026-07-30
Canary-only detour — ported forward, not `git revert`ed, so the new+used search
and hang/discard fixes added since stay intact. Milanuncios and Coches.net are
scraped here with their nationwide-Spain URLs (not Canarias-filtered) —
deterministic Stage A coverage for Spain only. Everything else — every other
European country, Autocasion, AutoScout24, and live search for new (0km) dealer
stock anywhere in Europe — has no deterministic scraper and is Stage B's job via
live WebSearch/WebFetch, per `Resources/europe-motorhome-selling-sites.md`.

Discarded listings (the 🗑 button -> Supabase `camper_hidden`) are excluded here,
so a discard means "never searched again", not merely "hidden in the UI".
"""
```

- [ ] **Step 4: Edit `fetch_milanuncios`**

Replace:

```python
def fetch_milanuncios(params: dict) -> list:
    """Scrape Milanuncios autocaravanas listings (Canary Islands only) via Playwright.

    Playwright is required because most cards are JS-rendered; plain requests only
    sees the 3 "destacado" cards.

    If selectors break, inspect article[data-testid="AD_CARD"] on
    milanuncios.com/autocaravanas-de-segunda-mano/canarias.htm and update below.
    2026-07-30: reinstated the canarias.htm suffix (verified live, 200 + real
    "Canarias" content) after the 2026-07-26 detour had widened this to nationwide.
    """
    max_weight = params.get("max_weight_kg", 99999)
    results = []

    url = "https://www.milanuncios.com/autocaravanas-de-segunda-mano/canarias.htm"
```

with:

```python
def fetch_milanuncios(params: dict) -> list:
    """Scrape Milanuncios autocaravanas listings (nationwide Spain) via Playwright.

    Playwright is required because most cards are JS-rendered; plain requests only
    sees the 3 "destacado" cards.

    If selectors break, inspect article[data-testid="AD_CARD"] on
    milanuncios.com/autocaravanas-de-segunda-mano/ and update below.
    2026-08-11: dropped the canarias.htm suffix (verified live via curl, 200 +
    real listing content) to restore Europe-wide scope — Spain is still the only
    country with a deterministic scraper; the rest of Europe is Stage B's job.
    """
    max_weight = params.get("max_weight_kg", 99999)
    results = []

    url = "https://www.milanuncios.com/autocaravanas-de-segunda-mano/"
```

- [ ] **Step 5: Edit `fetch_coches_net`**

Replace:

```python
def fetch_coches_net(params: dict) -> list:
    """Scrape coches.net autocaravanas listings (Canary Islands only) via Playwright.

    Bot-detection on coches.net is aggressive: requests that look headless get
    served an "Ups! Parece que algo no va bien..." stub page with zero cards.
    We use a humanlike browser context (locale, timezone, viewport, UA hint
    spoofing) which reliably yields cards on first-page load.

    Pagination via ?page=N is unreliable (typically returns 0 on page 2 even
    when the total count is higher), so we only scrape page 1.

    If selectors break, inspect div.mt-CardAd on
    coches.net/autocaravanas-y-remolques/canarias/ and update below. (2026-07-26:
    the category slug was renamed from autocaravanas-segunda-mano; the old path
    still redirects today but don't rely on that. 2026-07-30: reinstated the
    /canarias/ path segment — verified live, 200 + real "Canarias"/"provincia"
    content — after the 2026-07-26 detour had widened this to nationwide. This
    category carries dealer/0km stock alongside used listings, so it also covers
    part of the "new" side of the refocused brief.)
    """
    max_weight = params.get("max_weight_kg", 99999)
    results = []

    url = "https://www.coches.net/autocaravanas-y-remolques/canarias/?page=1"
```

with:

```python
def fetch_coches_net(params: dict) -> list:
    """Scrape coches.net autocaravanas listings (nationwide Spain) via Playwright.

    Bot-detection on coches.net is aggressive: requests that look headless get
    served an "Ups! Parece que algo no va bien..." stub page with zero cards.
    We use a humanlike browser context (locale, timezone, viewport, UA hint
    spoofing) which reliably yields cards on first-page load.

    Pagination via ?page=N is unreliable (typically returns 0 on page 2 even
    when the total count is higher), so we only scrape page 1.

    If selectors break, inspect div.mt-CardAd on
    coches.net/autocaravanas-y-remolques/ and update below. (2026-07-26: the
    category slug was renamed from autocaravanas-segunda-mano; the old path still
    redirects today but don't rely on that. 2026-08-11: dropped the /canarias/
    path segment — verified live via curl, 200 + real listing content — to
    restore Europe-wide scope. This category carries dealer/0km stock alongside
    used listings, so it also covers part of the "new" side of the brief.)
    """
    max_weight = params.get("max_weight_kg", 99999)
    results = []

    url = "https://www.coches.net/autocaravanas-y-remolques/?page=1"
```

- [ ] **Step 6: Run the new test to confirm it passes**

```bash
.venv/bin/python3 -m pytest tests/test_harvest.py::test_scrape_urls_are_nationwide_spain_not_canarias_filtered -v
```

Expected: PASS.

- [ ] **Step 7: Run the full `test_harvest.py` suite to confirm no regressions**

```bash
.venv/bin/python3 -m pytest tests/test_harvest.py -v
```

Expected: all PASS (this file's other tests exercise `fingerprint`/`same_vehicle`/blocklist logic, none of which touch the URL constants just changed).

- [ ] **Step 8: Commit**

```bash
git add scripts/harvest.py tests/test_harvest.py
git commit -m "feat: restore harvest.py Stage A scrapers to nationwide Spain"
```

---

### Task 3: Resources — swap active portal list from Canary to Europe

**Files:**
- Modify: `Resources/canary-motorhome-selling-sites.md` (add superseded banner)
- Modify: `Resources/europe-motorhome-selling-sites.md` (remove superseded banner, restore active; add a "New (0km) motorhomes" section generalized to Europe)

**Interfaces:** None — these are Stage B reference documents, not code. `scripts/weekly-search.sh` (Task 5) is what decides which file actually gets copied into Stage B's scratch dir; this task just prepares the file contents themselves.

**Context:** The project has a documented convention (used once already, 2026-07-30) of marking a superseded portal file "superseded" in-place at the top rather than deleting it. Do the same in reverse here: mark the Canary file superseded, and remove/replace the superseded banner on the Europe file. The Europe file also needs a "New (0km) motorhomes" section — the Canary file gained this section during the 2026-07-30 detour to support the (non-geography) new+used search addition, and that addition needs to carry forward into the restored Europe file too, generalized from island-specific dealer searches to per-country ones.

- [ ] **Step 1: Write the verification check (expect it to fail first)**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
grep -c "SUPERSEDED" Resources/canary-motorhome-selling-sites.md    # expect 0 (not yet marked)
grep -c "SUPERSEDED 2026-07-30" Resources/europe-motorhome-selling-sites.md   # expect 1 (still marked superseded)
grep -c "New (0km) motorhomes" Resources/europe-motorhome-selling-sites.md   # expect 0 (section doesn't exist yet)
```

- [ ] **Step 2: Mark `canary-motorhome-selling-sites.md` superseded**

Replace the file's first line and the blank line after it:

```markdown
# Canary Islands Motorhome Selling Sites

Added 2026-07-30, replacing `europe-motorhome-selling-sites.md` in the active
```

with:

```markdown
# Canary Islands Motorhome Selling Sites

**SUPERSEDED 2026-08-11** — Luis restored the project to Europe-wide scope
(used + new). This file is no longer read by `weekly-search.sh` or
`research-prompt.md`; see `europe-motorhome-selling-sites.md` instead. Left
here for reference only in case the Canary-only scope ever comes back.

Added 2026-07-30, replacing `europe-motorhome-selling-sites.md` in the active
```

- [ ] **Step 3: Un-supersede `europe-motorhome-selling-sites.md`**

Replace:

```markdown
# Europe Motorhome Selling Sites

**SUPERSEDED 2026-07-30** — Luis refocused the project to the Canary Islands
only (used + new). This file is no longer read by `weekly-search.sh` or
`research-prompt.md`; see `canary-motorhome-selling-sites.md` instead. Left
here for reference only in case the Europe-wide scope ever comes back.

This is a practical Europe-wide list of established websites for buying and selling motorhomes, campervans and caravans. "New" means dealer or manufacturer stock; "Used" means second-hand listings; "Both" means both are commonly available.
```

with:

```markdown
# Europe Motorhome Selling Sites

**Restored 2026-08-11** — active again as the master portal list for
`weekly-search.sh` / `research-prompt.md`, after a brief 2026-07-30 Canary-only
detour (see `canary-motorhome-selling-sites.md`, now itself marked
superseded). Also now covers new (0km/concesionario) stock, not just used —
see the "New (0km) motorhomes" section below, an addition from the detour
carried forward since it isn't geography-specific.

This is a practical Europe-wide list of established websites for buying and selling motorhomes, campervans and caravans. "New" means dealer or manufacturer stock; "Used" means second-hand listings; "Both" means both are commonly available.
```

- [ ] **Step 4: Add the "New (0km) motorhomes" section**

In `Resources/europe-motorhome-selling-sites.md`, find the `## Important checks when buying cross-border` heading (the last section in the file) and insert a new section immediately before it:

```markdown
## New (0km) motorhomes — active search required

There is no single reliable static list of every authorized new-vehicle dealer
across Europe, and one would go stale fast. Every run, Stage B must actively
**WebSearch** for current dealers rather than relying only on the tables above:

- `[marca] concesionario` / `[marca] Händler` / `[marca] dealer` for each brand
  in the model-family list in `research-prompt.md` (Benimar, Adria, Hymer,
  Bürstner, Rapido, Chausson, Challenger, Knaus, Carado, Sunlight, Dethleffs,
  Elnagh, Roller Team, Etrusco, etc.) — many manufacturers publish an online
  dealer locator that can be filtered by country.
- Coches.net and Autocasion (Spain/Portugal section above) both carry
  dealer/0km stock alongside used listings — don't skip them assuming they're
  used-only.
- CamperOnline (Italy) and YpoCamp/Hunyvers/CLC Loisirs (France) are
  dealer-network sites that list new stock directly.

## Important checks when buying cross-border
```

(The duplicate `## Important checks when buying cross-border` line above is intentional in this find/replace — it marks the insertion point; the result should have the new section followed immediately by the existing one, not two copies of the heading text you're inserting before.)

- [ ] **Step 5: Run the verification check to confirm it now passes**

```bash
grep -c "SUPERSEDED" Resources/canary-motorhome-selling-sites.md    # expect 1
grep -c "SUPERSEDED" Resources/europe-motorhome-selling-sites.md    # expect 0
grep -c "New (0km) motorhomes" Resources/europe-motorhome-selling-sites.md   # expect 1
```

- [ ] **Step 6: Commit**

```bash
git add Resources/canary-motorhome-selling-sites.md Resources/europe-motorhome-selling-sites.md
git commit -m "docs: restore europe-motorhome-selling-sites.md as active portal list"
```

---

### Task 4: Stage B — restore Europe-wide geography/logistics language in `research-prompt.md`

**Files:**
- Modify: `scripts/research-prompt.md` (full file, geography-specific sections only)

**Interfaces:** None — this is the Stage B (`claude -p`) prompt text, not code. Its only "interface" is the JSON contract it asks Stage B to write to `scripts/winners.json`, consumed by `scripts/apply_winners.py`. That contract's field names (`country`, `location`, `vat_status`, etc.) are unchanged by this task — only the values/description text for `country` and `vat_status` change back from Canary-only to Europe-wide.

**Context:** This file mixes geography-specific content (which gets reverted) with non-geography content added during the 2026-07-30 detour (which must be kept): the "search new stock too" instruction, the 0km/mileage-guidance carve-out, and the km-rule wording. The exact reverse of the 2026-07-30 diff is available via `git show fb2abff -- scripts/research-prompt.md` for reference, but do NOT apply it as a literal patch — several of its reverted lines need re-merging with the new+used additions rather than a clean revert. Each step below is hand-merged already.

- [ ] **Step 1: Write the verification check (expect it to fail first)**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
grep -c "toda Europa" scripts/research-prompt.md          # expect 0 (not yet restored)
grep -c "Islas Canarias\*\*" scripts/research-prompt.md    # expect nonzero (still Canary-scoped)
grep -c "busca ambos activamente" scripts/research-prompt.md   # expect 1 (new+used instruction present — must survive every edit below)
```

- [ ] **Step 2: Title/intro — restore Europe-wide scope**

Replace:

```markdown
Eres el investigador de autocaravanas de una familia. Tu trabajo hoy: elegir
**las 5 mejores autocaravanas en venta en las Islas Canarias** — nuevas
(0km/concesionario) o de segunda mano, cualquiera de las dos vale — y explicar
por qué.
```

with:

```markdown
Eres el investigador de autocaravanas de una familia. Tu trabajo hoy: elegir
**las 5 mejores autocaravanas en venta en toda Europa** — nuevas
(0km/concesionario) o de segunda mano, cualquiera de las dos vale — y explicar
por qué.
```

- [ ] **Step 3: "LA FAMILIA" section — restore pan-European framing**

Replace:

```markdown
Dos adultos, **un niño de 2,5 años y un bebé de 3 meses**. Viven en las Islas
Canarias y el vehículo se compra **dentro de las Islas Canarias** — Gran
Canaria, Tenerife, Lanzarote, Fuerteventura, La Palma, La Gomera, El Hierro,
La Graciosa. (2026-07-30: refocado a solo Canarias — si vienes de una versión
previa de este prompt que buscaba por toda Europa, no arrastres ese alcance;
un anuncio que exige traer el vehículo desde la península o el resto de
Europa queda fuera de alcance, no es "más lejos pero válido".) Un candidato en
otra isla distinta a la de residencia de la familia no es peor por eso — el
salto entre islas es un trayecto de ferry corto, no un coste real a
penalizar.
```

with:

```markdown
Dos adultos, **un niño de 2,5 años y un bebé de 3 meses**. Viven en las Islas
Canarias; el vehículo se comprará en cualquier punto de Europa. **La recogida y
el trayecto de vuelta hasta el sur de España son un viaje por carretera que la
familia hace por gusto — no es un servicio de transporte de pago.** Esto
importa para la puntuación (ver "Logística y coste real" más abajo): un
anuncio en Alemania, Francia, Italia o Países Bajos NO es peor que uno en
España solo por estar "más lejos". El único coste extra real, e igual para
cualquier candidato sea cual sea su país de origen, es el **ferry/RoRo de la
península a Canarias**. No inventes ni asumas un coste de transporte
proporcional a la distancia — no existe, porque el vehículo lo conduce la
propia familia. (2026-08-11: restaurado el alcance europeo — si vienes de una
versión previa de este prompt que buscaba solo en Canarias, no arrastres ese
alcance; un candidato en cualquier país de Europa es tan válido como uno en
Canarias o la península.)
```

- [ ] **Step 4: "Ya NO son requisitos eliminatorios" — restore the location bullet**

Replace:

```markdown
**Ya NO son requisitos eliminatorios** (antes lo eran en este proyecto):
- **Baño** — ahora es preferencia fuerte, no filtro (ver abajo).
- **Integral o perfilada únicamente** — la familia no ha pedido excluir ningún tipo
  de carrocería. Si una capuchina, camper van o cualquier otro tipo cumple los 5
  requisitos innegociables de arriba, es un candidato tan válido como cualquier
  perfilada o integral. No la descartes solo por el tipo de carrocería.
- **≥4 plazas para dormir como filtro aparte** — el encargo actual solo exige ≥4
  plazas de *viaje* con cinturón (arriba). Las plazas para dormir importan como
  preferencia (4ª/5ª plaza infantil, ver abajo), no como filtro eliminatorio propio.
```

with:

```markdown
**Ya NO son requisitos eliminatorios** (antes lo eran en este proyecto):
- **Baño** — ahora es preferencia fuerte, no filtro (ver abajo).
- **Ubicación en Canarias** — el alcance es toda Europa; un candidato en
  Canarias o en la península sigue siendo bienvenido, simplemente ya no es
  obligatorio.
- **Integral o perfilada únicamente** — la familia no ha pedido excluir ningún tipo
  de carrocería. Si una capuchina, camper van o cualquier otro tipo cumple los 5
  requisitos innegociables de arriba, es un candidato tan válido como cualquier
  perfilada o integral. No la descartes solo por el tipo de carrocería.
- **≥4 plazas para dormir como filtro aparte** — el encargo actual solo exige ≥4
  plazas de *viaje* con cinturón (arriba). Las plazas para dormir importan como
  preferencia (4ª/5ª plaza infantil, ver abajo), no como filtro eliminatorio propio.
```

(The "Parámetros" and "Regla de kilometraje" sections directly below this are untouched — they're the new+used addition and carry no geography content.)

- [ ] **Step 5: "Preferencias fuertes" — swap IGIC reference back to IVA**

Replace:

```markdown
- **IGIC** — ver "Logística e IGIC" más abajo.
```

with:

```markdown
- **IVA** — ver "Logística y coste real" más abajo.
```

- [ ] **Step 6: "Cómo ordenar" — restore European market framing**

Replace:

```markdown
Ordena por **valor global** — así lo pide la familia, sin fórmula ni porcentajes
fijos. No hay pesos predefinidos: usa tu juicio, comparando cada candidato contra
las preferencias fuertes y los extras de arriba (camas gemelas + kit, baño separado,
4ª/5ª plaza, historial de mantenimiento y sin humedad, IGIC/tipo de vendedor) y contra
lo que ese modelo/año realmente vale en el **mercado real** (no solo en la isla
donde está publicado — busca ese mismo modelo/año a la venta en otras islas o en
un concesionario nuevo, aplicando la regla de kilometraje de arriba a las unidades
de ocasión). Ningún factor individual manda sobre
los demás — es una valoración de conjunto, igual que pediría la familia si mirara los
anuncios ella misma.
```

with:

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

- [ ] **Step 7: "Logística e IGIC" — restore the two-section structure**

Replace:

```markdown
### Logística e IGIC (léelo antes de valorar cada candidato)

Al estar el vehículo ya dentro de las Islas Canarias, no hay transporte
continental ni ferry península-Canarias que valorar — esa era la lógica del
alcance europeo anterior y ya no aplica. Un salto entre islas (p.ej. el
comprador está en Gran Canaria y el vehículo en Tenerife) es, como mucho, un
trayecto corto en ferry inter-insular; no lo trates como un coste real ni
penalices un candidato por estar en otra isla.

Canarias está **fuera del territorio IVA de la UE**: las ventas aquí llevan
**IGIC**, no IVA, tanto para vehículos nuevos como de ocasión. No hay que
razonar ninguna importación — simplemente anota, para cada candidato, si el
precio anunciado incluye IGIC o no, y si el vendedor es particular o
concesionario oficial. Si no está publicado, márcalo como "a confirmar con el
vendedor" y sigue. Es un dato a registrar, no un filtro.
```

with:

```markdown
### Logística y coste real (léelo antes de valorar cada candidato)

La familia recoge el vehículo en persona y se lo lleva conduciendo hasta un puerto del
sur de España como parte de un viaje por carretera — no es un transporte contratado.
**No penalices ni un candidato alemán, francés, italiano u holandés frente a uno
español por la distancia**, y no inventes ni estimes un coste de transporte
proporcional al país de origen. El único coste añadido real, e igual para cualquier
candidato sea cual sea su país, es el **ferry RoRo desde la península hasta
Canarias** — trátalo como una constante, no como un factor diferenciador entre países
europeos. Esto aplica igual a unidades nuevas (0km/concesionario) y de segunda mano.

### IVA y Canarias

Canarias está en la unión aduanera pero **fuera del territorio IVA de la UE**, así que
enviar un vehículo allí es en principio una exportación que puede facturarse al 0% de
IVA, pagando el IGIC a la llegada — tanto si el vehículo es nuevo como de segunda
mano. Esto normalmente solo funciona con un **concesionario** dispuesto a gestionar
la documentación de exportación. No lo persigas activamente — para cada candidato,
simplemente anota si el vendedor es concesionario o particular, y si el IVA se indica
por separado. Si no está publicado, márcalo como "a confirmar con el vendedor" y
sigue. Es un plus, no un filtro.
```

- [ ] **Step 8: Step 1 instructions — restore nationwide framing and portal list**

Replace:

```markdown
### 1. Lee los candidatos ya recolectados
`scripts/candidates.json` — lo ha generado el harvester, que cubre Milanuncios y
Coches.net **filtrados a Canarias** (no nacional). Cada entrada trae `id`, `title`, `price`, `url`,
`source`. **Los datos de las fichas de resultados son pobres a propósito**: no
traen plazas, cinturones, distribución, volante, longitud ni MMA — por eso hace
falta abrir cada anuncio serio (paso 3).

El resto de fuentes — Wallapop, Autocasion, AutoScout24 España, RentCamper
Canarias, Autocaravanas Canarias, y cualquier concesionario de vehículos nuevos
(0km) — no tienen scraper propio todavía: los buscas tú mismo, en vivo, en el
siguiente paso.
```

with:

```markdown
### 1. Lee los candidatos ya recolectados
`scripts/candidates.json` — lo ha generado el harvester, que cubre Milanuncios y
Coches.net **a nivel nacional** (España entera, no solo Canarias). Cada entrada
trae `id`, `title`, `price`, `url`, `source`. **Los datos de las fichas de
resultados son pobres a propósito**: no traen plazas, cinturones, distribución,
volante, longitud ni MMA — por eso hace falta abrir cada anuncio serio (paso 3).

El resto de portales del encargo — mobile.de, AutoScout24, Marktplaats, leboncoin,
La Centrale, Subito.it, CamperOnLine, Autocasion, OLX, páginas de fabricante, y
cualquier concesionario de vehículos nuevos (0km) en cualquier país europeo — no
tienen scraper propio todavía: los buscas tú mismo, en vivo, en el siguiente paso.
```

- [ ] **Step 9: Discard-check paragraph — restore "por Europa" wording**

Replace:

```markdown
**Antes de dar por definitivo el resultado, respeta los descartes de la familia —
tan importante como los requisitos innegociables.** El botón 🗑 del dashboard
descarta un vehículo para siempre: el harvester ya lo excluye de
`candidates.json`, pero tu propia búsqueda en vivo (paso 2) puede volver a
encontrar ese mismo anuncio (misma URL, ya sin saber que fue descartado).
Antes de escribir `winners.json`, ejecuta esto por Bash:
```

with:

```markdown
**Antes de dar por definitivo el resultado, respeta los descartes de la familia —
tan importante como los requisitos innegociables.** El botón 🗑 del dashboard
descarta un vehículo para siempre: el harvester ya lo excluye de
`candidates.json`, pero tu propia búsqueda en vivo por Europa (paso 2) puede
volver a encontrar ese mismo anuncio (misma URL, ya sin saber que fue
descartado). Antes de escribir `winners.json`, ejecuta esto por Bash:
```

- [ ] **Step 10: Step 2 — restore the Europe-wide portal list and language table**

Replace the entire step 2 block:

```markdown
### 2. Busca de forma extensiva por todas las Islas Canarias — nuevas y de segunda mano
El harvester por sí solo no basta: el encargo pide una búsqueda extensiva, **nuevas
y de segunda mano por igual**, dentro de las Islas Canarias. Usa WebSearch y WebFetch.

**Portales:** abre `Resources/canary-motorhome-selling-sites.md` — es la lista
maestra de fuentes para este encargo (añadida 2026-07-30, sustituye a la antigua
lista europea). **Recórrela en el orden en que aparece en el fichero**: primero los
marketplaces generales filtrados a Canarias (Milanuncios, Coches.net, Wallapop,
Autocasion, AutoScout24 España), después los concesionarios canarios conocidos
(RentCamper Canarias, Autocaravanas Canarias), y por último las búsquedas activas de
vehículos **nuevos (0km)** — esta última parte no es opcional: no asumas que "nuevo"
solo aparecerá si te lo encuentras por casualidad, búscalo explícitamente (ver la
sección "New (0km) motorhomes" del fichero para las consultas concretas). Milanuncios
y Coches.net ya están cubiertos en parte por el harvester (paso 1); repásalos aquí
solo para lo que se les escape.

**Familias de modelos a revisar** (verifica cada una individualmente — los códigos de
distribución cambian según el año): Adria Matrix y Coral, Hymer Exsis-T y B-Klasse
ModernComfort, Bürstner Lyseo, Rapido, Chausson, Challenger, Weinsberg CaraSuite, Knaus
Van Ti y Sky Ti, Carado, Sunlight, Dethleffs Trend, Benimar Tessoro, Elnagh, Roller
Team, Etrusco — todas se venden nuevas o de ocasión en España/Canarias, así que
búscalas en ambos estados. Para las unidades **nuevas**, busca también el
concesionario oficial de cada marca en Canarias (`[marca] concesionario Canarias`).

Busca con la misma profundidad en cada portal y familia de modelos, y en ambos
estados (nuevo/ocasión) — el recorte va en el informe final, no en la búsqueda.
```

with:

```markdown
### 2. Busca por toda Europa — nuevas y de segunda mano
El mercado español por sí solo no basta: el encargo es **toda Europa**, y pide una
búsqueda extensiva **nuevas y de segunda mano por igual**. Usa WebSearch y WebFetch
en estos portales, con los términos nativos de cada idioma (el layout es lo difícil
de buscar, así que usa el término local, no la traducción literal):

**Portales:** abre `Resources/europe-motorhome-selling-sites.md` — es la lista
maestra de sitios de venta de autocaravanas en Europa. **Recórrela en el orden en
que aparece en el fichero**: empieza por la lista de prioridad (AutoScout24,
mobile.de, Caraworld, TruckScout24, Motorhome Depot, Leboncoin, Milanuncios,
AutoTrader UK, Marktplaats, Camping-Car.com) y después sigue por las secciones de
país en el orden del fichero (Reino Unido/Irlanda, Francia, España/Portugal, Italia,
Países Bajos/Bélgica, Alemania/Austria/Suiza, Escandinavia/Europa Central) hasta
agotar el presupuesto de fetches de abajo — no lo reordenes ni lo saltees a tu
criterio. Al final de esas secciones, incluye también las búsquedas activas de
vehículos **nuevos (0km)** de la sección "New (0km) motorhomes" del fichero — esta
parte no es opcional: no asumas que "nuevo" solo aparecerá si te lo encuentras por
casualidad, búscalo explícitamente en cada país relevante. Milanuncios/Coches.net/
Autocasion (ES) ya están cubiertos en parte por el harvester (paso 1); repásalos
aquí solo para lo que se les escape.

**Términos de búsqueda por concepto e idioma:**

| Concepto | DE | FR | IT | NL | ES |
|---|---|---|---|---|---|
| Camas gemelas traseras | Einzelbetten | lits jumeaux | letti gemelli | eenpersoonsbedden | camas gemelas |
| Kit de relleno / conversión | Bettverbreiterung, Mittelteil | kit de conversion lit central | kit trasformazione letti | tussenstuk | módulo central |
| Baño separado | separate Dusche, Raumbad | douche séparée | doccia separata | aparte douche | ducha separada |
| Integral/perfilada | Teilintegriert / Integriert | profilé / intégral | semintegrale / motorhome | halfintegraal | perfilada / integral |
| Vehículo nuevo/0km | Neufahrzeug | neuf | nuovo | nieuw | nuevo / 0km |

**Familias de modelos a revisar** (verifica cada una individualmente — los códigos de
distribución cambian según el año): Adria Matrix y Coral, Hymer Exsis-T y B-Klasse
ModernComfort, Bürstner Lyseo, Rapido, Chausson, Challenger, Weinsberg CaraSuite, Knaus
Van Ti y Sky Ti, Carado, Sunlight, Dethleffs Trend, Benimar Tessoro, Elnagh, Roller
Team, Etrusco — todas se venden nuevas o de ocasión en Europa, así que búscalas en
ambos estados. En los códigos alemanes, *EB*/*E* suele indicar *Einzelbetten*, pero
confírmalo siempre en el plano de distribución, nunca solo por el código. Para las
unidades **nuevas**, busca también el concesionario oficial de cada marca en el país
correspondiente (`[marca] concesionario` / `[marca] Händler` / `[marca] dealer`).

Busca con la misma profundidad en todos los portales, idiomas y familias, y en ambos
estados (nuevo/ocasión) — el recorte va en el informe final, no en la búsqueda.
```

(The "Disciplina de búsqueda" paragraph directly below step 2, and everything in step 3/step 4, are untouched by this step — only edit the block shown above.)

- [ ] **Step 11: Step 3 — restore European market-comparison wording**

Replace:

```markdown
Después **busca en la web ese modelo + año**: opiniones, fallos conocidos, problemas de
humedad, y a cuánto se vende ese mismo modelo (nuevo o de ocasión) en otras islas,
en concesionarios, o en el resto de España, para calibrar si el precio es real.
```

with:

```markdown
Después **busca en la web ese modelo + año**: opiniones, fallos conocidos, problemas de
humedad, y a cuánto se vende ese mismo modelo (nuevo o de ocasión) en otros países
europeos, para calibrar si el precio es real.
```

Also in step 3, replace:

```markdown
- si el vendedor es particular o concesionario oficial, y si el IGIC se indica por
  separado
```

with:

```markdown
- si el vendedor es particular o concesionario oficial, y si el IVA se indica por
  separado
```

- [ ] **Step 12: Output contract example — restore a European example listing**

Replace the example JSON block:

```json
[
  {
    "id": "autocaravanas_canarias-1a2b3c4d",
    "url": "https://...",
    "source": "autocaravanas_canarias",
    "title": "Roller Team Zefiro side — camas gemelas traseras",
    "price": 59900,
    "year": 2018,
    "km": 62000,
    "country": "España",
    "location": "Telde, Gran Canaria",
    "photo": "https://...",
    "dealer_or_private": "particular",
    "vat_status": "a confirmar con el vendedor",
    "checked_at": "2026-07-30",
    "rank": 1,
    "score": 87,
    "verdict": "Dos o tres frases en español. Por qué gana: distribución, precio real frente al mercado canario, y el pero más importante.",
    "flags": ["Solo he podido confirmar 2 cinturones de 3 puntos atrás — verificar con el vendedor"],
    "specs": {
      "seatbelts": 4,
      "berths": 4,
      "layout": "camas gemelas traseras con kit de relleno incluido",
      "bathroom_type": "separate",
      "mma_kg": 3500,
      "length_m": 6.95,
      "garage": true,
      "drive_side": "left",
      "bed_infill": "incluido",
      "payload_kg": 420
    }
  }
]
```

with:

```json
[
  {
    "id": "mobile_de-1a2b3c4d",
    "url": "https://...",
    "source": "mobile_de",
    "title": "Roller Team Zefiro side — camas gemelas traseras",
    "price": 59900,
    "year": 2018,
    "km": 62000,
    "country": "Alemania",
    "location": "Múnich",
    "photo": "https://...",
    "dealer_or_private": "particular",
    "vat_status": "a confirmar con el vendedor",
    "checked_at": "2026-08-11",
    "rank": 1,
    "score": 87,
    "verdict": "Dos o tres frases en español. Por qué gana: distribución, precio real frente al mercado europeo, y el pero más importante.",
    "flags": ["Solo he podido confirmar 2 cinturones de 3 puntos atrás — verificar con el vendedor"],
    "specs": {
      "seatbelts": 4,
      "berths": 4,
      "layout": "camas gemelas traseras con kit de relleno incluido",
      "bathroom_type": "separate",
      "mma_kg": 3500,
      "length_m": 6.95,
      "garage": true,
      "drive_side": "left",
      "bed_infill": "incluido",
      "payload_kg": 420
    }
  }
]
```

- [ ] **Step 13: Contract rules — restore `country`/`vat_status` descriptions**

Replace:

```markdown
- `country` — siempre `"España"` (alcance Canarias-only). `location` es el
  municipio + isla (p.ej. "Telde, Gran Canaria").
- `dealer_or_private` — `"concesionario"` o `"particular"`, o `null` si no se puede
  confirmar.
- `vat_status` — texto libre sobre el **IGIC** (p.ej. "IGIC incluido", "a confirmar
  con el vendedor"), o `null`. (El campo se llama `vat_status` por compatibilidad
  con el contrato anterior, pero en Canarias el impuesto real es el IGIC, no el IVA.)
```

with:

```markdown
- `country` — país del anuncio (p.ej. "Alemania", "Francia", "España"). `location`
  sigue significando la ciudad/región.
- `dealer_or_private` — `"concesionario"` o `"particular"`, o `null` si no se puede
  confirmar.
- `vat_status` — texto libre (p.ej. "IVA incluido", "a confirmar con el vendedor"), o
  `null`.
```

- [ ] **Step 14: Run the verification check to confirm it now passes**

```bash
grep -c "toda Europa" scripts/research-prompt.md          # expect >=2 (title + step 2 heading)
grep -c "Islas Canarias\*\*" scripts/research-prompt.md    # expect 0
grep -c "busca ambos activamente" scripts/research-prompt.md   # expect 1 — must still be there
grep -c "Ubicación en Canarias" scripts/research-prompt.md      # expect 1 — restored bullet
```

- [ ] **Step 15: Run the full test suite to confirm no regressions**

```bash
.venv/bin/python3 -m pytest tests/ -q
```

Expected: all PASS — `research-prompt.md` is prose, not imported by any test, so this just re-confirms nothing else broke.

- [ ] **Step 16: Commit**

```bash
git add scripts/research-prompt.md
git commit -m "feat: restore Europe-wide geography/logistics language in Stage B prompt"
```

---

### Task 5: `weekly-search.sh` — point Stage B at the Europe-wide portal file

**Files:**
- Modify: `scripts/weekly-search.sh` (header comment, portal-copy line + its comment, `STAGE_B_TIMEOUT` comment)

**Interfaces:** None — this only changes which file gets copied into `$STAGE_B_SCRATCH/Resources/`; the scratch-dir layout, watchdog mechanism, and single-03:00 schedule are all unchanged.

- [ ] **Step 1: Write the verification check (expect it to fail first)**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
grep -c "cp Resources/europe-motorhome-selling-sites.md" scripts/weekly-search.sh   # expect 0
```

- [ ] **Step 2: Update the header comment block**

Replace:

```bash
# The board is Top 5 (today) + Favorites (starred) — no week-by-week archive. Winners
# that don't repeat and aren't starred simply drop off; a day with nothing new
# re-picks the same winners, and Stage D's `git diff --cached --quiet` check means
# that publishes no new commit — a quiet day is a no-op, not noise. 2026-07-21:
# switched from Monday-only to daily at Luis's request; see MEMORY.md. 2026-07-30:
# refocused search scope to the Canary Islands only (used + new) and dropped the
# 07:00/13:00/19:00 retry slots down to a single 03:00 run at Luis's request — a
# Stage B failure (session limit, hang, flaky site) now has no same-day retry, the
# next attempt is tomorrow's 03:00. See MEMORY.md for the tradeoff and the known
# 03:20 Atlantic/Canary session-limit-reset timing risk.
```

with:

```bash
# The board is Top 5 (today) + Favorites (starred) — no week-by-week archive. Winners
# that don't repeat and aren't starred simply drop off; a day with nothing new
# re-picks the same winners, and Stage D's `git diff --cached --quiet` check means
# that publishes no new commit — a quiet day is a no-op, not noise. 2026-07-21:
# switched from Monday-only to daily at Luis's request; see MEMORY.md. 2026-07-30:
# refocused search scope to the Canary Islands only (used + new) and dropped the
# 07:00/13:00/19:00 retry slots down to a single 03:00 run at Luis's request — a
# Stage B failure (session limit, hang, flaky site) now has no same-day retry, the
# next attempt is tomorrow's 03:00. See MEMORY.md for the tradeoff and the known
# 03:20 Atlantic/Canary session-limit-reset timing risk. 2026-08-11: search scope
# restored to Europe-wide (see MEMORY.md) — the single-03:00 schedule and its
# no-same-day-retry tradeoff are unchanged, only the portal file Stage B reads
# (below) and harvest.py's scrape URLs changed.
```

- [ ] **Step 3: Swap the portal-file copy line**

Replace:

```bash
# The master portal list (research-prompt.md step 2 tells Stage B to work through
# it in order) — added 2026-07-28, replaced 2026-07-30 with the Canary-only list.
cp Resources/canary-motorhome-selling-sites.md "$STAGE_B_SCRATCH/Resources/canary-motorhome-selling-sites.md"
```

with:

```bash
# The master portal list (research-prompt.md step 2 tells Stage B to work through
# it in order) — added 2026-07-28, briefly replaced 2026-07-30 with a Canary-only
# list, restored 2026-08-11 to the Europe-wide list.
cp Resources/europe-motorhome-selling-sites.md "$STAGE_B_SCRATCH/Resources/europe-motorhome-selling-sites.md"
```

- [ ] **Step 4: Update the `STAGE_B_TIMEOUT` comment**

Replace:

```bash
STAGE_B_TIMEOUT=1500  # 25 min; the Canary-only source list (2026-07-30) is much shorter than the old Europe-wide one, so this should be generous — re-tune down if real runs consistently finish in a fraction of it
```

with:

```bash
STAGE_B_TIMEOUT=1500  # 25 min; unchanged by the 2026-08-11 Europe-wide restore (explicitly not widening the fetch budget) — re-tune if real runs start timing out against the larger portal list
```

- [ ] **Step 5: Syntax-check the script**

```bash
bash -n scripts/weekly-search.sh && echo "syntax OK"
```

Expected: `syntax OK`.

- [ ] **Step 6: Run the verification check to confirm it now passes**

```bash
grep -c "cp Resources/europe-motorhome-selling-sites.md" scripts/weekly-search.sh   # expect 1
grep -c "cp Resources/canary-motorhome-selling-sites.md" scripts/weekly-search.sh   # expect 0
```

- [ ] **Step 7: Commit**

```bash
git add scripts/weekly-search.sh
git commit -m "feat: point Stage B at the Europe-wide portal file again"
```

---

### Task 6: Docs — update `CLAUDE.md` and `README.md`

**Files:**
- Modify: `CLAUDE.md` (Purpose line, Portal list section, The rubric section)
- Modify: `README.md` (intro line, Cómo funciona table, La rúbrica section, Fuentes section)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Write the verification check (expect it to fail first)**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
grep -c "search scope is \*\*all of Europe\*\*" CLAUDE.md   # expect 0
grep -c "\*\*toda Europa\*\*" README.md                      # expect 0
```

- [ ] **Step 2: Edit `CLAUDE.md` — Purpose line**

Replace:

```markdown
**Purpose:** Find the best motorhome for a family of four (2 adults, a toddler and a
baby) — search scope is **the Canary Islands only** (2026-07-30: refocused back from
the brief Europe-wide period, reverting that geography while keeping everything else
learned since; see MEMORY.md), **new (0km/concesionario) or used, both searched
extensively**. Every day at 03:00 the pipeline searches, does deep research, and
publishes today's **Top 5** on the dashboard. The board is Top 5 (today) + Favorites
(starred) — no week-by-week archive (`board.py` dropped the ISO-week model
2026-07-26): a listing that drops out of the Top 5 and was never starred simply
disappears on the next run.
```

with:

```markdown
**Purpose:** Find the best motorhome for a family of four (2 adults, a toddler and a
baby) — search scope is **all of Europe** (2026-08-11: restored back from the brief
2026-07-30 Canary-only detour, porting the geography forward rather than reverting,
so new+used search and every non-geography fix since stays intact; see MEMORY.md),
**new (0km/concesionario) or used, both searched extensively**. Every day at 03:00
the pipeline searches, does deep research, and publishes today's **Top 5** on the
dashboard. The board is Top 5 (today) + Favorites (starred) — no week-by-week
archive (`board.py` dropped the ISO-week model 2026-07-26): a listing that drops
out of the Top 5 and was never starred simply disappears on the next run.
```

- [ ] **Step 3: Edit `CLAUDE.md` — Portal list section**

Replace:

```markdown
**Portal list**: `Resources/canary-motorhome-selling-sites.md` (added 2026-07-30,
replaces the 2026-07-28 Europe-wide file — which is left in the repo, marked
superseded at its top, not deleted) is the master list of Canary Islands selling
sources Stage B works through, in the order the file lists them (Canarias-filtered
marketplaces, then known local dealers, then active new-vehicle-dealer search).
`weekly-search.sh` copies it into the Stage B scratch dir alongside
`candidates.json`/`config.js` since Stage B runs isolated from the repo. Add new
sites there, not by editing the portal list inline in `research-prompt.md`.
```

with:

```markdown
**Portal list**: `Resources/europe-motorhome-selling-sites.md` (added 2026-07-28,
briefly superseded 2026-07-30 by a Canary-only file during that detour, restored
2026-08-11 — the Canary file is left in the repo, marked superseded at its top,
not deleted) is the master list of Europe-wide selling sources Stage B works
through, in the order the file lists them (priority list, then country sections,
then active new-vehicle-dealer search). `weekly-search.sh` copies it into the
Stage B scratch dir alongside `candidates.json`/`config.js` since Stage B runs
isolated from the repo. Add new sites there, not by editing the portal list
inline in `research-prompt.md`.
```

- [ ] **Step 4: Edit `CLAUDE.md` — The rubric section**

Replace:

```markdown
## The rubric

Family of four (2 adults, a 2.5-year-old, a 3-month-old). **Search scope is the
Canary Islands only** (2026-07-30: refocused back from the 2026-07-26 Europe-wide
brief at Luis's explicit request — geography reverted, but the rest of that
rebuild's lessons stay: no body-type restriction, no invented percentage scoring,
Top5+Favorites board model). **Both new (0km/concesionario) and used are searched
extensively** — this is new relative to the pre-2026-07-26 Canary-only rubric,
which was used-only. Hard gates: MAM ≤3,500 kg (B licence), **length ≥ 6.90 m**
(⚠️ this is unchanged from the Europe-wide period — do not revert to the old ≤7m
preference, that number was never re-requested), twin rear beds convertible to a
double via a factory infill kit, **left-hand drive**, ≥4 forward-facing
3-point-belt travel seats. Bathroom (separate preferred) and a 4th/5th child berth
remain strong preferences, not hard gates. Logistics note: no more pan-European
self-drive/ferry framing — the vehicle is already in the islands, so the only
geography-driven logistics that matter are an inter-island ferry hop (trivial,
not a scoring factor) and IGIC vs IVA (Canarias is outside the EU VAT area).

**No body-type restriction** — carried over from the 2026-07-26 rebuild, still
correct: don't exclude capuchinas/campervans or require integral/perfilada.
**No invented percentage scoring** — same, "rank by overall value" with no
weights/formula. **2 harvested sources, now Canarias-filtered** (2026-07-30) —
`harvest.py`'s `SOURCES` is still just Milanuncios + Coches.net, but both URLs
were switched back to their Canarias-only filter (`.../canarias.htm` and
`.../canarias/` respectively — recovered from git history, verified live) instead
of the nationwide-Spain URLs the 2026-07-26 rebuild had widened them to. Everything
else — Wallapop, Autocasion, AutoScout24 España, RentCamper Canarias, Autocaravanas
Canarias, and live search for new-vehicle dealers — is Stage B's job (live
WebSearch/WebFetch), same division of labor as before.

Full rubric: `scripts/research-prompt.md`.
```

with:

```markdown
## The rubric

Family of four (2 adults, a 2.5-year-old, a 3-month-old). **Search scope is all of
Europe** (2026-08-11: restored from the 2026-07-30 Canary-only detour, ported
forward rather than reverted — geography goes back to Europe-wide, but every
non-geography lesson from both the 2026-07-26 rebuild and the Canary detour
stays: no body-type restriction, no invented percentage scoring, Top5+Favorites
board model, and new+used search). **Both new (0km/concesionario) and used are
searched extensively** — this started as a Canary-only-detour addition
(2026-07-30) and is kept now that scope is Europe-wide again; the original
2026-07-26 Europe-wide brief had been used-only. Hard gates: MAM ≤3,500 kg (B
licence), **length ≥ 6.90 m** (⚠️ do not revert to the old ≤7m preference, that
number was never re-requested), twin rear beds convertible to a double via a
factory infill kit, **left-hand drive**, ≥4 forward-facing 3-point-belt travel
seats. Bathroom (separate preferred) and a 4th/5th child berth remain strong
preferences, not hard gates. Logistics note: pan-European self-drive/ferry
framing is back — buy anywhere in Europe, self-drive it back, ferry only the
Canary leg (no distance/shipping-cost penalty by country) — and IVA/IGIC import
notes replace the local-IGIC-only note from the Canary detour.

**No body-type restriction** — carried over from the 2026-07-26 rebuild, still
correct: don't exclude capuchinas/campervans or require integral/perfilada.
**No invented percentage scoring** — same, "rank by overall value" with no
weights/formula. **2 harvested sources, nationwide Spain again** (2026-08-11) —
`harvest.py`'s `SOURCES` is still just Milanuncios + Coches.net, and both URLs
are back to their nationwide-Spain form (no `/canarias.htm` or `/canarias/`
suffix — re-verified live via curl before landing, since they'd sat unused for
12 days). Everything else — every other European country, Autocasion, AutoScout24,
and live search for new-vehicle dealers anywhere in Europe — is Stage B's job
(live WebSearch/WebFetch), same division of labor as before.

Full rubric: `scripts/research-prompt.md`.
```

- [ ] **Step 5: Edit `README.md` — intro line**

Replace:

```markdown
**Top 5** de hoy — autocaravanas **nuevas y de segunda mano** en venta en las
**Islas Canarias** para una familia de 4 (2 adultos + 2 peques), buscadas y
valoradas a diario.
```

with:

```markdown
**Top 5** de hoy — autocaravanas **nuevas y de segunda mano** en venta en
**toda Europa** para una familia de 4 (2 adultos + 2 peques), buscadas y
valoradas a diario.
```

- [ ] **Step 6: Edit `README.md` — Cómo funciona table**

Replace:

```markdown
| **A · Harvest** (`scripts/harvest.py`) | Rastrea Milanuncios y Coches.net filtrados a Canarias. Determinista, sin IA. | `scripts/candidates.json` |
| **B · Investigación** (`claude -p` + `scripts/research-prompt.md`) | Abre cada anuncio, busca de forma extensiva en toda Canarias (nuevas y de segunda mano), compara con el mercado real, y puntúa contra la rúbrica familiar. | `scripts/winners.json` |
```

with:

```markdown
| **A · Harvest** (`scripts/harvest.py`) | Rastrea Milanuncios y Coches.net a nivel nacional (España). Determinista, sin IA. | `scripts/candidates.json` |
| **B · Investigación** (`claude -p` + `scripts/research-prompt.md`) | Abre cada anuncio, busca de forma extensiva por toda Europa (nuevas y de segunda mano), compara con el mercado real, y puntúa contra la rúbrica familiar. | `scripts/winners.json` |
```

- [ ] **Step 7: Edit `README.md` — La rúbrica section**

Replace:

```markdown
## La rúbrica

Familia de 4 (2 adultos, un niño de 2,5 años y un bebé de 3 meses). Búsqueda
**solo dentro de las Islas Canarias** (2026-07-30: refocado desde el periodo
Europa-wide) — **nuevas (0km/concesionario) y de segunda mano por igual**.
```

with:

```markdown
## La rúbrica

Familia de 4 (2 adultos, un niño de 2,5 años y un bebé de 3 meses). Búsqueda
**por toda Europa** (2026-08-11: restaurada tras un breve paréntesis
Canarias-only) — **nuevas (0km/concesionario) y de segunda mano por igual**.
```

- [ ] **Step 8: Edit `README.md` — Fuentes section**

Replace:

```markdown
## Fuentes

**Deterministas (Stage A)** — Milanuncios y Coches.net, vía Playwright (con
anti-bot en Coches.net), filtrados a Canarias.

**Canarias, en vivo (Stage B)** — Wallapop, Autocasion, AutoScout24 España, y los
concesionarios canarios conocidos (RentCamper Canarias, Autocaravanas Canarias),
más búsqueda activa de concesionarios de vehículos nuevos por isla. Sin scraper
dedicado todavía — lista completa en `Resources/canary-motorhome-selling-sites.md`.
```

with:

```markdown
## Fuentes

**Deterministas (Stage A)** — Milanuncios y Coches.net, vía Playwright (con
anti-bot en Coches.net), a nivel nacional (España).

**Europa, en vivo (Stage B)** — el resto de portales europeos (mobile.de,
AutoScout24, leboncoin, Marktplaats, Subito, Autocasion...) más búsqueda activa
de concesionarios de vehículos nuevos por país. Sin scraper dedicado todavía —
lista completa en `Resources/europe-motorhome-selling-sites.md`.
```

- [ ] **Step 9: Run the verification check to confirm it now passes**

```bash
grep -c "search scope is \*\*all of Europe\*\*" CLAUDE.md   # expect 1
grep -c "\*\*toda Europa\*\*" README.md                      # expect 1
```

- [ ] **Step 10: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLAUDE.md and README.md for the Europe-wide restore"
```

---

### Task 7: Run the full test suite

**Files:** None modified — this is the validation-plan step 1 checkpoint.

**Interfaces:** None.

- [ ] **Step 1: Run the full suite**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
.venv/bin/python3 -m pytest tests/ -v
```

Expected: all tests PASS, including the new `test_scrape_urls_are_nationwide_spain_not_canarias_filtered` from Task 2. If anything fails, stop and diagnose before moving to Task 8 — do not run the real pipeline against a codebase with a known-failing test.

- [ ] **Step 2: No commit needed** — this task makes no changes, it's a checkpoint.

---

### Task 8: End-to-end pipeline run

**Files:** None modified directly — this task exercises Stages A-D as they now stand after Tasks 2-5. It writes `scripts/candidates.json`, `scripts/winners.json`, `docs/listings.json`, and (on success) creates a git commit + push via `weekly-search.sh` itself.

**Interfaces:** None new.

**Context:** This is the design spec's validation step 2: force a real run today to confirm the restored pipeline actually harvests, researches (via a real `claude -p` Stage B call, budget ~25-30 fetches, up to the 25-minute watchdog), and publishes Europe-wide results. This costs real wall-clock time (historically 6-25 minutes) and one Stage B `claude -p` invocation (counts against Claude session usage) — run it deliberately, not as a background afterthought.

- [ ] **Step 1: Force a re-run by clearing today's marker**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
TODAY="$(date '+%Y-%m-%d')"
rm -f ".state/$TODAY.done"
ls .state/ | grep "$TODAY" || echo "marker cleared"
```

- [ ] **Step 2: Run the pipeline directly (not via launchd) to watch it live**

```bash
./scripts/weekly-search.sh
tail -100 ~/Library/Logs/motorhome-daily.log
```

This blocks until Stage B finishes or the 25-minute watchdog kills it. Watch for `--- Stage A`, `--- Stage B`, `--- Stage C`, `--- Stage D` markers in the log.

- [ ] **Step 3: Confirm Stage A pulled from nationwide Spain, not Canarias**

```bash
.venv/bin/python3 -c "
import json
c = json.load(open('scripts/candidates.json'))
print(f'{len(c)} candidates')
locs = [x.get('location','') for x in c if x.get('location')]
print('sample locations:', locs[:10])
"
```

Expected: a candidate count noticeably higher than the ~35-45-unit Canary-only ceiling documented in MEMORY.md (nationwide Spain is a much bigger market), and locations not exclusively Canary place-names.

- [ ] **Step 4: Confirm Stage B actually ran Europe-wide, not Canary-scoped**

```bash
cat scripts/winners.json | python3 -m json.tool | head -60
```

Expected: `country` fields showing non-Spain values are plausible (Germany/France/Italy/Netherlands, not exclusively "España"), and `location` values are city/region names, not Canary Islands names exclusively. It's fine if this particular day's actual Top 5 happens to include a Spanish or even Canary listing — the check is that Stage B was *not artificially restricted* to Spain, not that every winner must be foreign.

- [ ] **Step 5: Confirm the log shows no FATAL and the run published**

```bash
tail -30 ~/Library/Logs/motorhome-daily.log
```

Expected: no `FATAL:` lines, and either "Pushed. Pages live in ~60s." or "No change to publish." (the latter is fine if today's winners happen to match what was already on the board — an unlikely but not impossible outcome for the first run after a scope change).

- [ ] **Step 6: If Stage B failed or hung, do not proceed to Task 9**

If the watchdog killed Stage B or `winners.json` was never produced, read the hang-sample file it produces (`.state/hang-sample-*.txt`) and/or the log's FATAL line, fix the underlying issue, and re-run from Step 1. Do not force a manual `apply_winners.py` run against a stale/hand-edited `winners.json` just to get past this task — the point of this task is confirming the *real* pipeline works end-to-end.

---

### Task 9: Spot-check the published board and update `MEMORY.md`

**Files:**
- Modify: `MEMORY.md` (new dated entry, "Last reviewed" line)

**Interfaces:** None.

- [ ] **Step 1: Spot-check the JSON that will render**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
.venv/bin/python3 -c "
import json
l = json.load(open('docs/listings.json'))
print(f'{len(l)} entries on the board')
for e in l:
    print(e.get('rank'), e.get('title'), '|', e.get('location'), '|', e.get('price'))
"
```

Expected: entries present, each with a title/location/price, `rank` 1-5 for non-favorited entries or `null` for favorites — no crash, no empty required fields.

- [ ] **Step 2: Load the live dashboard and confirm it renders**

Use the playwriter CLI (per the global CLAUDE.md's browser-automation rule — always via the CLI, never `mcp__playwriter__execute`) to open https://commanderwi11.github.io/Motorhome_Search/ about 60-90 seconds after Stage D's push, and confirm:
- The Top 5 section shows cards (not an empty state or a JS error).
- At least one card's location/country is plausibly non-Canary (confirms the Europe-wide scope reached the actual rendered page, not just the JSON).
- The Favoritos section (if any favorites are currently starred) still renders correctly — confirms this change didn't disturb favorite-listing rendering.

If playwriter/Chrome isn't available in this session, fall back to `curl -s https://commanderwi11.github.io/Motorhome_Search/docs/listings.json` (or the equivalent raw GitHub Pages URL for `listings.json`) and re-run the Step 1 JSON check against the live, deployed file instead of the local one — confirming Stage D's push actually reached Pages, not just the local git repo.

- [ ] **Step 3: Write the `MEMORY.md` entry**

Add a new dated section near the top of `MEMORY.md` (immediately after the `# Motorhome Lifestyle Memory` / `Last reviewed:` header, before the `## 2026-07-31` entry), following the file's existing entry format. Fill in the actual observed results from Tasks 8-9 (candidate count, winners found, any surprises) rather than the placeholder text below — this is illustrative of the shape, not the literal content to paste:

```markdown
## 2026-08-11 — Europe-wide search scope restored

Luis asked to widen the automated pipeline's search back to all of Europe —
the Canary Islands market is genuinely thin (~35-45 units per prior research),
and the real fix for recall is geography, not more Canary-specific sources.
Approved design doc: `docs/superpowers/specs/2026-08-11-europe-wide-search-restore-design.md`.

**Why:** the 2026-07-30 Canary-only refocus (see that entry below) was a
deliberate scope narrowing, not a mistake — but it left recall thin. Ported
forward rather than `git revert`ed, to keep every non-geography fix layered on
since (new+used search, Top5+Favorites model, discard defense-in-depth, hang
mitigation).

**What changed:**
- `scripts/harvest.py` — `fetch_milanuncios`/`fetch_coches_net` URLs back to
  nationwide Spain (no `/canarias.htm`, no `/canarias/`), re-verified live via
  curl before wiring in.
- `Resources/europe-motorhome-selling-sites.md` — un-superseded, restored as
  the active portal list; gained a new "New (0km) motorhomes" section
  (generalized from the Canary file's version) since new-vehicle search is
  now a permanent feature, not Canary-specific.
  `Resources/canary-motorhome-selling-sites.md` marked superseded in place,
  not deleted.
- `scripts/research-prompt.md` — Europe-wide geography/logistics language
  restored (buy anywhere in Europe, self-drive + Canary ferry leg only,
  IVA/IGIC import note). Hard gates, budget, no-body-type-filter,
  no-invented-scoring, and the new+used search instruction all unchanged.
- `scripts/weekly-search.sh` — Stage B scratch dir now copies
  `europe-motorhome-selling-sites.md`. Single 03:00 schedule, watchdog timeout,
  and the 03:20 Atlantic/Canary session-limit-reset risk are all unchanged.
- Docs: `CLAUDE.md`, `README.md` updated for consistency.
- Repo hygiene: deleted two confirmed-stale iCloud conflict copies
  (`docs/history 2.json`, `scripts/ingest_manual_shortlist 2.py`) after
  diffing them against their real counterparts (0 unique lines in either) and
  getting Luis's go-ahead.
- **Validation**: full test suite passed (including a new test pinning the
  restored URLs). Ran a real end-to-end pipeline pass (cleared today's
  `.state` marker first) — [FILL IN: candidate count, winners found, any
  countries represented, whether it published]. Spot-checked the live
  dashboard renders correctly.

**Not part of this change** (explicitly out of scope per the design doc):
wider Stage B fetch budget, dedicated scrapers for more sources (mobile.de,
AutoScout24, etc. — still Stage B's live-search job), distance/shipping-cost
scoring.
```

- [ ] **Step 4: Update the "Last reviewed" date and Status checklist**

In `MEMORY.md`, update `Last reviewed: 2026-07-31` to `Last reviewed: 2026-08-11`, and in the `## Status` section, add a line after the existing Canary-refocus line:

```markdown
- [x] Refocused to Canary Islands only, new+used, single 03:00 run (2026-07-30, see above)
- [x] Restored to Europe-wide scope, new+used, single 03:00 run kept (2026-08-11, see above)
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/openbob/Library/Mobile Documents/com~apple~CloudDocs/AI Coworking/01_Personal_HQ/Projects/Motorhome_HQ/Motorhome_Search"
git add MEMORY.md
git commit -m "docs(memory): record 2026-08-11 Europe-wide search restore"
```

- [ ] **Step 6: Report back to Luis**

Summarize: what changed, the real Stage A candidate count and Stage B winner countries from Task 8, and confirmation the live dashboard renders. This closes out the design spec's three-part validation plan (test suite, end-to-end run, dashboard spot-check).
