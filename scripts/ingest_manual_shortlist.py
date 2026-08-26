#!/usr/bin/env python3
"""Ingest a manually-researched Top 5 shortlist into docs/history.json.

Luis periodically runs a deep, multi-portal search by hand (or via a separate
Claude session doing live WebFetch/browser research) covering sites the
automated harvester can't reach — Fotocasa, pisos.com, direct estate-agent
sites, etc. He pastes the result as a markdown table; this script is where
that gets transcribed into structured data and folded into the dashboard's
"history" view.

This is a SEPARATE, additive concept from docs/listings.json's Top 5 +
Favorites model — it does not touch listings.json, board.py, or the daily
automated pipeline at all. history.json is just a per-date archive of these
manual research snapshots, shown on the dashboard below the automated
Top 5 + Favorites. See docs/app.js's history rendering and CLAUDE.md.

Usage: edit SHORTLISTS below with the next dated batch (title/price/bedrooms/
location/size_m2 per entry, transcribed by hand from the pasted markdown —
pasted tables sometimes arrive with OCR/copy corruption in cells and URLs;
cross-reference against other dates' mentions of the same listing before
trusting a truncated cell), then run this file. Re-running for a date already
in history.json replaces that date's entries (idempotent).
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from harvest import make_id, fetch_og_image  # noqa: E402

HISTORY_FILE = Path(__file__).parent.parent / "docs" / "history.json"

# Add the next dated batch here, e.g.:
# "2026-09-01": [
#     {"url": "...", "title": "...", "price": 480000, "bedrooms": 3,
#      "location": "Tafira, Las Palmas de Gran Canaria", "size_m2": 180},
# ],
SHORTLISTS = {
}


def source_from_url(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").replace(".", "_")


def build_entry(raw: dict, photo_cache: dict) -> dict:
    url = raw["url"]
    source = source_from_url(url)
    if url not in photo_cache:
        photo_cache[url] = fetch_og_image(url)
    return {
        "id": make_id(source, url),
        "url": url,
        "source": source,
        "title": raw["title"],
        "price": raw["price"],
        "location": raw["location"],
        "photo": photo_cache[url],
        "specs": {
            "bedrooms": raw.get("bedrooms"),
            "size_m2": raw.get("size_m2"),
            "has_garden": raw.get("has_garden"),
        },
    }


def main():
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    by_date = {h["date"]: h for h in history}
    photo_cache = {}

    for date, raw_entries in SHORTLISTS.items():
        entries = [build_entry(r, photo_cache) for r in raw_entries]
        by_date[date] = {"date": date, "entries": entries}
        print(f"{date}: {len(entries)} entries "
              f"({sum(1 for e in entries if e['photo'])} with photo)")

    history = sorted(by_date.values(), key=lambda h: h["date"], reverse=True)
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {HISTORY_FILE}")


if __name__ == "__main__":
    main()
