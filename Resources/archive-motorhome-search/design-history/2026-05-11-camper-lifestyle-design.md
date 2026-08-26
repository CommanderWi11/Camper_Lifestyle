# Camper Life-style — Design Spec
_Date: 2026-05-11_

## Purpose

A personal family tool to track, evaluate, and comment on camper-van listings available in the Canary Islands. Two users: Luis and his wife. Goal: decide on the best camper-van to buy.

---

## Search Parameters

Stored in `scripts/params.json`. Filters applied by the weekly script:

| Parameter | Value |
|---|---|
| Max price | €55,000 |
| Min sleeping capacity | 4 (2 adults, 2 kids) |
| Bathroom with shower | Required |
| Max vehicle age | 10 years (≥ 2015) |
| Max mileage | 100,000 km |
| Market | Canary Islands only |
| Reference model | Sunlight Cliff Adventure |
| Sources | Wallapop, Milanuncios, Autoscout24.es |

---

## Architecture

### Overview

```
Camper_Lifestyle/
├── CLAUDE.md
├── MEMORY.md
├── dashboard/              ← published as separate GitHub repo (camper-lifestyle)
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── config.js           ← Supabase anon key + URL (not committed)
│   └── listings.json       ← source of truth for all tracked listings
├── scripts/
│   ├── search.py           ← weekly scraper
│   └── params.json         ← search filter definitions
├── .github/
│   └── workflows/
│       └── weekly-search.yml
├── Resources/
│   └── reference-models.md
└── docs/superpowers/specs/
    └── 2026-05-11-camper-lifestyle-design.md
```

The `dashboard/` folder is synced to a dedicated public GitHub repo (`camper-lifestyle`) and served via GitHub Pages. Everything else stays in the AI Coworking monorepo.

---

## Components

### 1. `listings.json`

Source of truth. Each entry:

```json
{
  "id": "wallapop-12345",
  "title": "Sunlight Cliff Adventure 640 2019",
  "price": 48500,
  "year": 2019,
  "km": 67000,
  "sleeping": 4,
  "bathroom": true,
  "location": "Las Palmas de Gran Canaria",
  "source": "wallapop",
  "url": "https://...",
  "photo": "https://...",
  "status": "new",
  "added_at": "2026-05-11"
}
```

`status` values: `new` | `watching` | `contacted` | `discarded`

Script sets `"status": "new"` on first insert. User changes status manually via the dashboard. Existing entries are never overwritten by the script.

---

### 2. `search.py`

Weekly scraper. Behaviour:
1. Reads `params.json`
2. Queries Wallapop, Milanuncios, Autoscout24.es
3. Filters results against all parameters
4. Merges into `listings.json` — existing entries are never overwritten (preserves `status` and Supabase comment linkage)
5. Marks genuinely new entries with `"new": true`
6. Commits updated `listings.json` to trigger GitHub Pages rebuild

---

### 3. `weekly-search.yml` (GitHub Actions)

- Cron: every Monday at 08:00 UTC
- Also triggerable manually via `workflow_dispatch`
- Steps: checkout → install deps → run `search.py` → commit + push if changed

---

### 4. Dashboard (`index.html` + `app.js`)

**Layout:**
- Header: title + "Last updated: [date]" + filter/sort bar
- Filter bar: status filter (All / New / Watching / Contacted / Discarded), sort by price or date
- Listing cards grid, each card contains:
  - Photo
  - Title, price, year, km, location
  - Bathroom badge
  - Status badge (colour-coded)
  - Link to original listing
  - Comment section: existing comments (author, text, date) + submit form (Name + text + button)

**app.js behaviour:**
- On load: fetch `listings.json`, fetch all comments from Supabase for visible listing IDs
- On comment submit: insert row to Supabase `comments` table, re-render that card's comments
- No page reload required for comments

---

### 5. Supabase Comments Table

Reuses the existing **Family_Plan Supabase project**.

```sql
create table camper_comments (
  id uuid default gen_random_uuid() primary key,
  listing_id text not null,
  author text not null,
  body text not null,
  created_at timestamptz default now()
);

alter table camper_comments enable row level security;
create policy "anon read" on camper_comments for select using (true);
create policy "anon insert" on camper_comments for insert with check (true);
```

Table named `camper_comments` (not `comments`) to avoid collision with any existing Family_Plan tables.

`config.js` (not committed, added to `.gitignore`):
```js
const SUPABASE_URL = "https://<project>.supabase.co";
const SUPABASE_ANON_KEY = "<anon-key>";
```

---

## Data Flow

```
GitHub Actions (Monday 08:00)
  → search.py reads params.json
  → scrapes Wallapop / Milanuncios / Autoscout24.es
  → merges into listings.json
  → commits → GitHub Pages rebuilds dashboard

User visits dashboard
  → app.js fetches listings.json (static)
  → app.js fetches camper_comments from Supabase
  → renders cards with comments

User submits comment
  → app.js inserts to Supabase camper_comments
  → re-renders card comments
```

---

## Out of Scope

- Authentication / login (anon access is sufficient for a private family URL)
- Mobile app
- Price alerts / push notifications
- Integration with dealer contact forms
