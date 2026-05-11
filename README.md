# Camper Life-style

Family camper-van research dashboard. Tracks listings from Wallapop and Milanuncios
in the Canary Islands. Weekly search via GitHub Actions. Comments via Supabase.

## Setup

1. Copy `dashboard/config.js.example` → `dashboard/config.js` and fill in Supabase credentials
2. Install Python deps: `pip install -r scripts/requirements.txt`
3. Run manually: `python scripts/search.py`
4. GitHub Pages: configure repo Settings → Pages → Branch: main, Folder: /docs

## Search parameters

Edit `scripts/params.json` to change filters.
