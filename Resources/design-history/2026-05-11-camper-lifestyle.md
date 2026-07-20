# Camper Life-style Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a family camper-van research dashboard (GitHub Pages) with a weekly automated search script and Supabase-backed collaborative comments.

**Architecture:** `camper-lifestyle` is a standalone GitHub repo (separate from AI Coworking). The `dashboard/` folder is published via GitHub Pages. A Python scraper runs weekly via GitHub Actions and commits updated `listings.json` to the repo, which triggers Pages to rebuild. Comments are stored in the existing Family_Plan Supabase project and fetched client-side.

**Tech Stack:** Python 3.11 + requests + BeautifulSoup4 (scraper), vanilla HTML/CSS/JS (dashboard), Supabase JS v2 via CDN (comments), GitHub Actions (scheduling + CI), GitHub Pages (hosting)

---

## File Map

```
camper-lifestyle/                  ← standalone GitHub repo
├── dashboard/
│   ├── index.html                 ← main UI shell
│   ├── style.css                  ← all styles
│   ├── app.js                     ← fetch listings + render + comments
│   ├── config.js                  ← Supabase URL + anon key (gitignored)
│   ├── config.js.example          ← template committed to repo
│   └── listings.json              ← source of truth for all listings
├── scripts/
│   ├── search.py                  ← weekly scraper (Wallapop + Milanuncios)
│   ├── params.json                ← all search filter parameters
│   └── requirements.txt           ← pip deps
├── tests/
│   └── test_search.py             ← pytest tests for search.py logic
├── .github/
│   └── workflows/
│       └── weekly-search.yml      ← cron: Monday 08:00 UTC
├── .gitignore
└── README.md

01_Personal_HQ/Projects/Camper_Lifestyle/   ← AI Coworking reference only
├── CLAUDE.md
├── MEMORY.md
└── docs/superpowers/
    ├── specs/2026-05-11-camper-lifestyle-design.md
    └── plans/2026-05-11-camper-lifestyle.md  ← this file
```

---

## Task 1: GitHub repo + project scaffolding

**Files (in `camper-lifestyle/`):**
- Create: `.gitignore`
- Create: `README.md`
- Create: `scripts/requirements.txt`
- Create: `dashboard/config.js.example`
- Create (AI Coworking): `01_Personal_HQ/Projects/Camper_Lifestyle/CLAUDE.md`
- Create (AI Coworking): `01_Personal_HQ/Projects/Camper_Lifestyle/MEMORY.md`

- [ ] **Step 1: Create the GitHub repo**

Go to github.com → New repository → name: `camper-lifestyle` → Public → no README (we'll push one). Clone it locally outside AI Coworking:

```bash
cd ~/Developer   # or wherever you keep repos
git clone git@github.com:<your-username>/camper-lifestyle.git
cd camper-lifestyle
```

- [ ] **Step 2: Create `.gitignore`**

```
dashboard/config.js
__pycache__/
*.pyc
*.pyo
.env
.DS_Store
```

- [ ] **Step 3: Create `scripts/requirements.txt`**

```
requests==2.31.0
beautifulsoup4==4.12.3
```

- [ ] **Step 4: Create `dashboard/config.js.example`**

```js
// Copy this file to config.js and fill in your Supabase credentials.
// config.js is gitignored — never commit the real keys.
// The anon key is safe to use client-side; RLS policies control access.
const SUPABASE_URL = "https://YOUR_PROJECT.supabase.co";
const SUPABASE_ANON_KEY = "YOUR_ANON_KEY";
```

- [ ] **Step 5: Create `README.md`**

```markdown
# Camper Life-style

Family camper-van research dashboard. Tracks listings from Wallapop and Milanuncios
in the Canary Islands. Weekly search via GitHub Actions. Comments via Supabase.

## Setup

1. Copy `dashboard/config.js.example` → `dashboard/config.js` and fill in Supabase credentials
2. Install Python deps: `pip install -r scripts/requirements.txt`
3. Run manually: `python scripts/search.py`
4. GitHub Pages: configure repo Settings → Pages → Branch: main, Folder: /dashboard

## Search parameters

Edit `scripts/params.json` to change filters.
```

- [ ] **Step 6: Create `CLAUDE.md` in AI Coworking project folder**

Path: `01_Personal_HQ/Projects/Camper_Lifestyle/CLAUDE.md`

```markdown
# Camper Life-style

**Purpose:** Family tool to track and evaluate camper-van listings in the Canary Islands.

**Code repo:** github.com/<your-username>/camper-lifestyle (separate from AI Coworking)
Clone at: ~/Developer/camper-lifestyle/

**Dashboard URL:** https://<your-username>.github.io/camper-lifestyle/

**Supabase:** Family_Plan project — table: camper_comments

## Working in this project

Always `cd ~/Developer/camper-lifestyle` before editing code.
This AI Coworking folder contains planning docs only (CLAUDE.md, MEMORY.md, spec, plan).
```

- [ ] **Step 7: Create `MEMORY.md` in AI Coworking project folder**

Path: `01_Personal_HQ/Projects/Camper_Lifestyle/MEMORY.md`

```markdown
# Camper Life-style Memory

Last reviewed: 2026-05-11

## Status
- [ ] Project scaffolding
- [ ] Search script
- [ ] Dashboard
- [ ] GitHub Pages live

## Key decisions
- Standalone GitHub repo (not inside AI Coworking monorepo)
- GitHub Pages serves dashboard/ folder from main branch
- Supabase: Family_Plan project, table: camper_comments
- Wallapop + Milanuncios as sources (Autoscout24 deferred)
- No auth — anon insert/select on camper_comments with RLS

## Search parameters
- Budget: ≤ €55,000
- Sleeping: ≥ 4
- Bathroom + shower: required
- Max age: 10 years (≥ 2015)
- Max km: 100,000
- Market: Canary Islands
- Reference: Sunlight Cliff Adventure
```

- [ ] **Step 8: Commit scaffold**

```bash
mkdir -p dashboard scripts tests .github/workflows
git add .
git commit -m "chore: initial project scaffold"
git push origin main
```

---

## Task 2: Search parameters + seed listing

**Files:**
- Create: `scripts/params.json`
- Create: `dashboard/listings.json`

- [ ] **Step 1: Create `scripts/params.json`**

```json
{
  "max_price": 55000,
  "min_sleeping": 4,
  "requires_bathroom": true,
  "max_age_years": 10,
  "max_km": 100000,
  "location": "Canarias",
  "keywords": ["camper", "autocaravana", "campervan", "furgoneta camper"],
  "reference_models": ["Sunlight Cliff", "Cliff Adventure"],
  "wallapop": {
    "latitude": 28.1235,
    "longitude": -15.4366,
    "distance_km": 500
  }
}
```

- [ ] **Step 2: Create `dashboard/listings.json` with one seed entry**

The seed entry serves as a live reference to the target model. It will never be overwritten by the script because it has status `watching`.

```json
[
  {
    "id": "manual-sunlight-ref",
    "title": "Referencia: Sunlight Cliff Adventure 640",
    "price": 0,
    "year": 2024,
    "km": 0,
    "sleeping": 4,
    "bathroom": true,
    "location": "Modelo nuevo (referencia)",
    "source": "manual",
    "url": "https://www.sunlight.de/es/modelos/camper-vans/cliff-adventure/",
    "photo": "",
    "status": "watching",
    "added_at": "2026-05-11"
  }
]
```

- [ ] **Step 3: Commit**

```bash
git add scripts/params.json dashboard/listings.json
git commit -m "feat: add search params and seed listing"
git push origin main
```

---

## Task 3: search.py — full implementation

**Files:**
- Create: `scripts/search.py`

- [ ] **Step 1: Create `scripts/search.py`**

```python
#!/usr/bin/env python3
"""Weekly camper-van search for Canary Islands listings."""

import json
import hashlib
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PARAMS_FILE = Path(__file__).parent / "params.json"
LISTINGS_FILE = Path(__file__).parent.parent / "dashboard" / "listings.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def load_params() -> dict:
    return json.loads(PARAMS_FILE.read_text())


def load_listings() -> list:
    if LISTINGS_FILE.exists():
        return json.loads(LISTINGS_FILE.read_text())
    return []


def save_listings(listings: list) -> None:
    LISTINGS_FILE.write_text(json.dumps(listings, ensure_ascii=False, indent=2))


def make_id(source: str, url: str) -> str:
    return f"{source}-{hashlib.md5(url.encode()).hexdigest()[:8]}"


def fetch_wallapop(params: dict) -> list:
    """Query Wallapop JSON API. Returns list of raw listing dicts."""
    wp = params["wallapop"]
    endpoint = "https://api.wallapop.com/api/v3/general/search"
    results = []

    for keyword in params["keywords"]:
        try:
            resp = requests.get(
                endpoint,
                params={
                    "keywords": keyword,
                    "latitude": wp["latitude"],
                    "longitude": wp["longitude"],
                    "distance": wp["distance_km"] * 1000,
                    "max_sale_price": params["max_price"],
                    "order_by": "newest",
                    "category_ids": "100",  # vehicles category
                },
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("search_objects", []):
                slug = item.get("web_slug", "")
                url = f"https://es.wallapop.com/item/{slug}"
                results.append({
                    "id": make_id("wallapop", url),
                    "title": item.get("title", "").strip(),
                    "price": int(item.get("price", 0)),
                    "year": None,
                    "km": None,
                    "sleeping": None,
                    "bathroom": None,
                    "location": item.get("location", {}).get("city", ""),
                    "source": "wallapop",
                    "url": url,
                    "photo": item.get("main_image", {}).get("urls", {}).get("big", ""),
                    "status": "new",
                    "added_at": str(date.today()),
                })
        except Exception as exc:
            print(f"[wallapop] error for '{keyword}': {exc}", file=sys.stderr)

    return results


def fetch_milanuncios(params: dict) -> list:
    """Scrape Milanuncios search results.

    NOTE: CSS selectors are brittle. If this stops working, inspect
    milanuncios.com/autocaravanas-y-campers/ in a browser and update
    the selectors below (look for article and price elements).
    """
    results = []

    for keyword in params["keywords"][:2]:  # limit to avoid rate limiting
        try:
            url = (
                f"https://www.milanuncios.com/autocaravanas-y-campers/"
                f"?texto={requests.utils.quote(keyword)}"
                f"&lp={params['max_price']}&porloca=5"
            )
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for article in soup.select("article.ma-AdCard"):
                title_el = article.select_one(".ma-AdCard-title")
                price_el = article.select_one(".ma-AdPrice-value")
                location_el = article.select_one(".ma-AdLocation-text")
                link_el = article.select_one("a.ma-AdCard-titleLink")
                img_el = article.select_one("img.ma-AdCard-photo")

                if not title_el or not price_el or not link_el:
                    continue

                price_str = (
                    price_el.get_text(strip=True)
                    .replace(".", "")
                    .replace(",", "")
                    .replace("€", "")
                    .strip()
                )
                try:
                    price = int(price_str)
                except ValueError:
                    continue

                if price > params["max_price"]:
                    continue

                href = link_el.get("href", "")
                full_url = (
                    f"https://www.milanuncios.com{href}"
                    if href.startswith("/")
                    else href
                )

                results.append({
                    "id": make_id("milanuncios", full_url),
                    "title": title_el.get_text(strip=True),
                    "price": price,
                    "year": None,
                    "km": None,
                    "sleeping": None,
                    "bathroom": None,
                    "location": location_el.get_text(strip=True) if location_el else "",
                    "source": "milanuncios",
                    "url": full_url,
                    "photo": img_el.get("src", "") if img_el else "",
                    "status": "new",
                    "added_at": str(date.today()),
                })
        except Exception as exc:
            print(f"[milanuncios] error for '{keyword}': {exc}", file=sys.stderr)

    return results


def merge_listings(existing: list, new_results: list) -> list:
    """Add new listings without overwriting any existing entry."""
    existing_ids = {item["id"] for item in existing}
    added = 0
    for item in new_results:
        if item["id"] not in existing_ids:
            existing.append(item)
            existing_ids.add(item["id"])
            added += 1
    print(f"Added {added} new listings. Total: {len(existing)}")
    return existing


def main() -> None:
    params = load_params()
    existing = load_listings()

    print("Fetching Wallapop...")
    wallapop = fetch_wallapop(params)

    print("Fetching Milanuncios...")
    milanuncios = fetch_milanuncios(params)

    merged = merge_listings(existing, wallapop + milanuncios)
    save_listings(merged)
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run manually to verify it doesn't crash**

```bash
cd ~/Developer/camper-lifestyle
pip install -r scripts/requirements.txt
python scripts/search.py
```

Expected output:
```
Fetching Wallapop...
Fetching Milanuncios...
Added N new listings. Total: N+1
Done.
```

Inspect `dashboard/listings.json` — seed entry should still be present, new entries appended.

- [ ] **Step 3: Commit**

```bash
git add scripts/search.py
git commit -m "feat: add weekly search script (Wallapop + Milanuncios)"
git push origin main
```

---

## Task 4: Tests for search.py

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_search.py`

- [ ] **Step 1: Create `tests/__init__.py`** (empty file)

- [ ] **Step 2: Write `tests/test_search.py`**

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add scripts/ to path so we can import search
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import search


def test_make_id_is_deterministic():
    assert search.make_id("wallapop", "https://example.com/item/123") == \
           search.make_id("wallapop", "https://example.com/item/123")


def test_make_id_differs_by_source():
    assert search.make_id("wallapop", "https://x.com") != \
           search.make_id("milanuncios", "https://x.com")


def test_make_id_differs_by_url():
    assert search.make_id("wallapop", "https://x.com/1") != \
           search.make_id("wallapop", "https://x.com/2")


def test_merge_adds_new_listing():
    existing = [{"id": "a-001", "title": "Old", "status": "watching"}]
    new = [{"id": "b-002", "title": "New", "status": "new"}]
    result = search.merge_listings(existing, new)
    assert len(result) == 2


def test_merge_skips_duplicate_id():
    existing = [{"id": "a-001", "title": "Old", "status": "watching"}]
    new = [{"id": "a-001", "title": "Updated", "status": "new"}]
    result = search.merge_listings(existing, new)
    assert len(result) == 1
    assert result[0]["title"] == "Old"  # existing entry preserved unchanged


def test_merge_preserves_status():
    existing = [{"id": "a-001", "status": "contacted"}]
    new = [{"id": "a-001", "status": "new"}]
    result = search.merge_listings(existing, new)
    assert result[0]["status"] == "contacted"


def test_fetch_wallapop_handles_network_error():
    params = {
        "max_price": 55000,
        "keywords": ["camper"],
        "wallapop": {"latitude": 28.1, "longitude": -15.4, "distance_km": 500},
    }
    with patch("search.requests.get", side_effect=Exception("Network error")):
        results = search.fetch_wallapop(params)
    assert results == []


def test_fetch_wallapop_returns_listings():
    params = {
        "max_price": 55000,
        "keywords": ["camper"],
        "wallapop": {"latitude": 28.1, "longitude": -15.4, "distance_km": 500},
    }
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "search_objects": [{
            "web_slug": "camper-van-12345",
            "title": "Camper Van Test",
            "price": 35000,
            "location": {"city": "Las Palmas"},
            "main_image": {"urls": {"big": "https://img.example.com/photo.jpg"}},
        }]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("search.requests.get", return_value=mock_response):
        results = search.fetch_wallapop(params)

    assert len(results) == 1
    assert results[0]["title"] == "Camper Van Test"
    assert results[0]["price"] == 35000
    assert results[0]["source"] == "wallapop"
    assert results[0]["status"] == "new"


def test_fetch_milanuncios_handles_network_error():
    params = {
        "max_price": 55000,
        "keywords": ["camper"],
    }
    with patch("search.requests.get", side_effect=Exception("Network error")):
        results = search.fetch_milanuncios(params)
    assert results == []
```

- [ ] **Step 3: Run tests — verify all pass**

```bash
cd ~/Developer/camper-lifestyle
pip install pytest
pytest tests/ -v
```

Expected: all 9 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add pytest suite for search.py merge and fetch logic"
git push origin main
```

---

## Task 5: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/weekly-search.yml`

- [ ] **Step 1: Create `.github/workflows/weekly-search.yml`**

```yaml
name: Weekly Camper Search

on:
  schedule:
    - cron: '0 8 * * 1'   # Every Monday at 08:00 UTC
  workflow_dispatch:        # Allow manual trigger from GitHub Actions tab

jobs:
  search:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r scripts/requirements.txt

      - name: Run search script
        run: python scripts/search.py

      - name: Commit and push if listings changed
        run: |
          git config --global user.name 'camper-bot'
          git config --global user.email 'bot@noreply.github.com'
          git add dashboard/listings.json
          git diff --cached --quiet || (
            git commit -m "chore: weekly listings update $(date +%Y-%m-%d)" &&
            git push
          )
```

- [ ] **Step 2: Commit and push — verify Actions tab shows the workflow**

```bash
git add .github/workflows/weekly-search.yml
git commit -m "ci: add weekly search GitHub Actions workflow"
git push origin main
```

Go to `github.com/<your-username>/camper-lifestyle/actions` and confirm the workflow appears. Run it manually via "Run workflow" button to test end-to-end.

---

## Task 6: Dashboard HTML + CSS

**Files:**
- Create: `dashboard/index.html`
- Create: `dashboard/style.css`

- [ ] **Step 1: Create `dashboard/index.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Camper Life-style</title>
  <link rel="stylesheet" href="style.css">
  <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  <script src="config.js"></script>
</head>
<body>
  <header>
    <div class="header-inner">
      <div>
        <h1>Camper Life-style</h1>
        <p class="subtitle">Buscando nuestra furgoneta perfecta</p>
      </div>
      <div class="header-params">
        <span>≤ 55.000 €</span>
        <span>4 plazas</span>
        <span>Baño</span>
        <span>≤ 100.000 km</span>
        <span>≤ 10 años</span>
      </div>
    </div>
  </header>

  <div class="toolbar">
    <div class="filters">
      <label>
        Estado
        <select id="filter-status">
          <option value="">Todos</option>
          <option value="new">Nuevo</option>
          <option value="watching">Siguiendo</option>
          <option value="contacted">Contactado</option>
          <option value="discarded">Descartado</option>
        </select>
      </label>
      <label>
        Ordenar por
        <select id="sort-by">
          <option value="added_at">Más reciente</option>
          <option value="price">Precio (menor)</option>
        </select>
      </label>
    </div>
    <div class="meta" id="last-updated"></div>
  </div>

  <main id="listings-grid">
    <p class="loading">Cargando anuncios...</p>
  </main>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `dashboard/style.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f0;
  color: #222;
  line-height: 1.5;
}

/* Header */
header {
  background: #1a1a2e;
  color: white;
  padding: 1.5rem;
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

header h1 { font-size: 1.6rem; font-weight: 700; }
.subtitle { opacity: 0.65; font-size: 0.9rem; margin-top: 0.2rem; }

.header-params {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.header-params span {
  background: rgba(255,255,255,0.12);
  border-radius: 12px;
  padding: 0.25rem 0.7rem;
  font-size: 0.78rem;
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.85rem 1.5rem;
  background: white;
  border-bottom: 1px solid #e8e8e0;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.filters { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: center; }

.filters label {
  font-size: 0.82rem;
  color: #666;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.filters select {
  padding: 0.3rem 0.6rem;
  border: 1px solid #d0d0c8;
  border-radius: 5px;
  font-size: 0.82rem;
  background: white;
}

.meta { font-size: 0.78rem; color: #aaa; }
.loading { color: #999; padding: 2rem 1.5rem; }

/* Grid */
main {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 1.25rem;
  padding: 1.5rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* Card */
.card {
  background: white;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 1px 8px rgba(0,0,0,0.04);
  display: flex;
  flex-direction: column;
}

.card-photo {
  width: 100%;
  height: 200px;
  object-fit: cover;
  display: block;
  background: #eeeee8;
}

.card-photo--empty {
  height: 200px;
  background: linear-gradient(135deg, #f0f0e8 0%, #e8e8e0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 2.5rem;
}

.card-body {
  padding: 1rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.card-title {
  font-size: 0.97rem;
  font-weight: 600;
  line-height: 1.35;
}

.card-title a {
  color: #1a1a2e;
  text-decoration: none;
}

.card-title a:hover { text-decoration: underline; }

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.card-meta span {
  font-size: 0.8rem;
  background: #f5f5f0;
  color: #555;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}

.source {
  text-transform: capitalize;
  color: #999 !important;
  background: transparent !important;
  font-size: 0.75rem !important;
}

/* Badges */
.badge {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 10px;
  white-space: nowrap;
  flex-shrink: 0;
}

.badge-new      { background: #fff3cd; color: #856404; }
.badge-watching { background: #cfe2ff; color: #084298; }
.badge-contacted{ background: #d1e7dd; color: #0a3622; }
.badge-discarded{ background: #f8d7da; color: #842029; }
.badge-feature  { background: #e8f4f8; color: #0c5460; }

/* Comments */
.comments {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  flex: 1;
}

.comment {
  padding: 0.45rem 0.65rem;
  background: #f8f8f5;
  border-radius: 6px;
  font-size: 0.83rem;
}

.comment strong { color: #1a1a2e; }

.comment-date {
  color: #bbb;
  font-size: 0.72rem;
  margin-left: 0.4rem;
}

.comment p { margin-top: 0.2rem; color: #444; }

/* Comment form */
.comment-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding-top: 0.6rem;
  border-top: 1px solid #f0f0e8;
  margin-top: auto;
}

.comment-form input,
.comment-form textarea {
  padding: 0.4rem 0.6rem;
  border: 1px solid #ddd;
  border-radius: 5px;
  font-size: 0.83rem;
  font-family: inherit;
  resize: vertical;
  background: #fafaf8;
}

.comment-form input:focus,
.comment-form textarea:focus {
  outline: none;
  border-color: #1a1a2e;
}

.comment-form button {
  align-self: flex-end;
  padding: 0.35rem 1rem;
  background: #1a1a2e;
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 0.82rem;
  transition: background 0.15s;
}

.comment-form button:hover { background: #2d2d50; }
.comment-form button:disabled { background: #999; cursor: default; }

@media (max-width: 480px) {
  main { grid-template-columns: 1fr; padding: 1rem; }
  .header-inner { flex-direction: column; align-items: flex-start; }
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/index.html dashboard/style.css
git commit -m "feat: add dashboard HTML and CSS"
git push origin main
```

---

## Task 7: app.js — listings + Supabase comments

**Files:**
- Create: `dashboard/app.js`

- [ ] **Step 1: Create `dashboard/app.js`**

```javascript
const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

let allListings = [];
let commentsByListing = {};

const STATUS_LABELS = {
  new: 'Nuevo',
  watching: 'Siguiendo',
  contacted: 'Contactado',
  discarded: 'Descartado',
};

const STATUS_CLASSES = {
  new: 'badge-new',
  watching: 'badge-watching',
  contacted: 'badge-contacted',
  discarded: 'badge-discarded',
};

async function init() {
  const [listings, commentsResult] = await Promise.all([
    fetch('listings.json').then(r => r.json()),
    supabaseClient.from('camper_comments').select('*').order('created_at', { ascending: true }),
  ]);

  allListings = listings;

  if (commentsResult.data) {
    for (const comment of commentsResult.data) {
      if (!commentsByListing[comment.listing_id]) {
        commentsByListing[comment.listing_id] = [];
      }
      commentsByListing[comment.listing_id].push(comment);
    }
  }

  const dates = allListings.map(l => l.added_at).filter(Boolean).sort().reverse();
  if (dates.length) {
    document.getElementById('last-updated').textContent = `Actualizado: ${dates[0]}`;
  }

  document.getElementById('filter-status').addEventListener('change', render);
  document.getElementById('sort-by').addEventListener('change', render);

  render();
}

function render() {
  const statusFilter = document.getElementById('filter-status').value;
  const sortBy = document.getElementById('sort-by').value;

  let listings = [...allListings];

  if (statusFilter) {
    listings = listings.filter(l => l.status === statusFilter);
  }

  if (sortBy === 'price') {
    listings.sort((a, b) => a.price - b.price);
  } else {
    listings.sort((a, b) => (b.added_at || '').localeCompare(a.added_at || ''));
  }

  const grid = document.getElementById('listings-grid');
  grid.innerHTML = listings.length
    ? listings.map(renderCard).join('')
    : '<p class="loading">No hay anuncios con ese filtro.</p>';

  grid.querySelectorAll('.comment-form').forEach(form => {
    form.addEventListener('submit', handleCommentSubmit);
  });
}

function renderCard(listing) {
  const comments = commentsByListing[listing.id] || [];
  const price = listing.price > 0
    ? `${listing.price.toLocaleString('es-ES')} €`
    : '—';

  return `
    <article class="card" data-id="${listing.id}">
      ${listing.photo
        ? `<img class="card-photo" src="${listing.photo}" alt="${listing.title}" loading="lazy">`
        : `<div class="card-photo card-photo--empty">🚐</div>`
      }
      <div class="card-body">
        <div class="card-header">
          <h2 class="card-title">
            <a href="${listing.url}" target="_blank" rel="noopener noreferrer">${listing.title}</a>
          </h2>
          <span class="badge ${STATUS_CLASSES[listing.status] || ''}">
            ${STATUS_LABELS[listing.status] || listing.status}
          </span>
        </div>

        <div class="card-meta">
          <span>💶 ${price}</span>
          ${listing.year ? `<span>📅 ${listing.year}</span>` : ''}
          ${listing.km ? `<span>🛣️ ${listing.km.toLocaleString('es-ES')} km</span>` : ''}
          ${listing.bathroom ? `<span class="badge badge-feature">🚿 Baño</span>` : ''}
          ${listing.sleeping ? `<span>🛏️ ${listing.sleeping} plazas</span>` : ''}
          ${listing.location ? `<span>📍 ${listing.location}</span>` : ''}
          <span class="source">${listing.source}</span>
        </div>

        <div class="comments" id="comments-${listing.id}">
          ${comments.map(renderComment).join('')}
        </div>

        <form class="comment-form" data-listing-id="${listing.id}">
          <input name="author" placeholder="Tu nombre" required maxlength="50" autocomplete="name">
          <textarea name="body" placeholder="¿Qué te parece este anuncio?" required maxlength="500" rows="2"></textarea>
          <button type="submit">Comentar</button>
        </form>
      </div>
    </article>
  `;
}

function renderComment(comment) {
  const date = new Date(comment.created_at).toLocaleDateString('es-ES', {
    day: 'numeric', month: 'short', year: 'numeric',
  });
  return `
    <div class="comment">
      <strong>${escapeHtml(comment.author)}</strong>
      <span class="comment-date">${date}</span>
      <p>${escapeHtml(comment.body)}</p>
    </div>
  `;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function handleCommentSubmit(e) {
  e.preventDefault();
  const form = e.target;
  const listingId = form.dataset.listingId;
  const author = form.author.value.trim();
  const body = form.body.value.trim();
  const btn = form.querySelector('button');

  btn.disabled = true;
  btn.textContent = 'Guardando...';

  const { data, error } = await supabaseClient
    .from('camper_comments')
    .insert({ listing_id: listingId, author, body })
    .select()
    .single();

  btn.disabled = false;
  btn.textContent = 'Comentar';

  if (error) {
    alert('Error al guardar el comentario. Inténtalo de nuevo.');
    return;
  }

  if (!commentsByListing[listingId]) commentsByListing[listingId] = [];
  commentsByListing[listingId].push(data);

  document.getElementById(`comments-${listingId}`).insertAdjacentHTML(
    'beforeend',
    renderComment(data),
  );

  form.reset();
}

init();
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app.js
git commit -m "feat: add dashboard app.js with listings render and Supabase comments"
git push origin main
```

---

## Task 8: Supabase table + config.js + GitHub Pages

**Files:**
- Create: `dashboard/config.js` (gitignored — never committed)

- [ ] **Step 1: Create the Supabase table**

Open the Family_Plan Supabase project SQL editor and run:

```sql
create table camper_comments (
  id uuid default gen_random_uuid() primary key,
  listing_id text not null,
  author text not null,
  body text not null,
  created_at timestamptz default now()
);

alter table camper_comments enable row level security;

create policy "anon select" on camper_comments
  for select using (true);

create policy "anon insert" on camper_comments
  for insert with check (
    length(author) > 0 and length(author) <= 50 and
    length(body) > 0 and length(body) <= 500
  );
```

- [ ] **Step 2: Create `dashboard/config.js` locally**

Get your Supabase URL and anon key from Family_Plan project → Settings → API:

```js
const SUPABASE_URL = "https://YOUR_PROJECT.supabase.co";
const SUPABASE_ANON_KEY = "YOUR_ANON_KEY_HERE";
```

Verify it is gitignored:
```bash
git check-ignore -v dashboard/config.js
```

Expected: `dashboard/config.js` should be listed as ignored.

- [ ] **Step 3: Configure GitHub Pages**

In the `camper-lifestyle` GitHub repo → Settings → Pages:
- Source: Deploy from a branch
- Branch: `main`
- Folder: `/dashboard`
- Click Save

Wait ~60 seconds. Your dashboard will be live at:
`https://<your-username>.github.io/camper-lifestyle/`

- [ ] **Step 4: Open the dashboard and verify**

- Listings load from `listings.json` (seed entry should appear)
- Filter and sort controls work
- Comment form submits to Supabase without error
- Posted comment appears immediately below the card

- [ ] **Step 5: Add GitHub Actions secret for `config.js` (optional but recommended)**

For the workflow to be able to run fully automated (no manual config.js), add secrets to the repo:

Go to repo Settings → Secrets → Actions → New repository secret:
- `SUPABASE_URL` = your URL
- `SUPABASE_ANON_KEY` = your anon key

Then update `.github/workflows/weekly-search.yml` to generate `config.js` before committing (optional enhancement — safe to skip for now since the script does not use Supabase).

- [ ] **Step 6: Update AI Coworking MEMORY.md with live URLs**

Edit `01_Personal_HQ/Projects/Camper_Lifestyle/MEMORY.md`:
- Mark "GitHub Pages live" as done
- Add the live dashboard URL
- Add the Supabase table confirmation

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "chore: confirm GitHub Pages and Supabase setup"
git push origin main
```

---

## Done

The project is live when:
- `https://<username>.github.io/camper-lifestyle/` shows the seed listing
- A test comment posts and persists on refresh
- The GitHub Actions workflow runs successfully on manual trigger and commits new listings
