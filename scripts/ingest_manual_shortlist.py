#!/usr/bin/env python3
"""Ingest a manually-researched Top 5 shortlist into docs/history.json.

Luis periodically runs a deep, multi-portal search by hand (or via a separate
Claude session doing live WebFetch/browser research) covering sites the
automated harvester can't reach — mobile.de, AutoScout24, leboncoin,
Marktplaats, Subito, etc. He pastes the result as a markdown table; this
script is where that gets transcribed into structured data and folded into
the dashboard's "history" view.

This is a SEPARATE, additive concept from docs/listings.json's Top 5 +
Favorites model — it does not touch listings.json, board.py, or the daily
automated pipeline at all. history.json is just a per-date archive of these
manual research snapshots, shown on the dashboard below the automated
Top 5 + Favorites. See docs/app.js's history rendering and CLAUDE.md.

Usage: edit SHORTLISTS below with the next dated batch (title/price/km/
location/length_m per entry, transcribed by hand from the pasted markdown —
some of Luis's pasted tables arrive with OCR/copy corruption in cells and
URLs; cross-reference against other dates' mentions of the same listing
before trusting a truncated cell), then run this file. Re-running for a date
already in history.json replaces that date's entries (idempotent).
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent))
from harvest import make_id, fetch_og_image  # noqa: E402

HISTORY_FILE = Path(__file__).parent.parent / "docs" / "history.json"

# 2026-07-24 / 07-25 / 07-27: three dated Top-5 shortlists pasted by Luis,
# transcribed here. Rows carried over unchanged across dates (Dethleffs Just Go
# T7055 EB in all three; Etrusco T7400 SBC and Sunlight T680 in 07-25+07-27)
# reuse the exact same URL each time, on purpose -- make_id() then produces the
# same id, so starring/deleting one instance collapses across every date.
SHORTLISTS = {
    "2026-07-24": [
        {
            "url": "https://www.camperonline.it/camper-usati/semintegrale-c-i-horon-87-xt_195896",
            "title": "C.I. Horon 87 XT (2025, casi nueva) - ducha separada, litera abatible",
            "price": 64900, "km": 7350, "location": "Monza (MB), Italia", "length_m": 7.45,
        },
        {
            "url": "https://www.caravanmarket.com/camper-mclouis-mc4-373",
            "title": "McLouis MC4 373 (2026, nueva) - 5 plazas homologadas, litera abatible",
            "price": 70580, "km": 0, "location": "Castel San Pietro Terme (BO), Italia", "length_m": 7.45,
        },
        {
            "url": "https://www.trovocamper.it/tessoro-t-463-letti-gemelli-5-posti-annuncio-263710",
            "title": "Benimar Tessoro T463 (2026, nueva) - 5 plazas, 5 literas",
            "price": 64900, "km": 0, "location": "Spinea (VE), Italia", "length_m": 7.43,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - camas gemelas + kit de relleno, automatica",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/lmc-tourer-t-660-g/367233.html",
            "title": "LMC Tourer T 660 G (2025, practicamente nueva) - la mas manejable, bano separado",
            "price": 69900, "km": 10, "location": "Moulay (53), Francia", "length_m": 6.99,
        },
    ],
    "2026-07-25": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "Etrusco T 7400 SBC (2023) - todo confirmado en el anuncio + litera electrica extra",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/sunlight-t-680-adventure-edition/384817.html",
            "title": "Sunlight T 680 Adventure Edition (2024) - 5 plazas homologadas, bano separado",
            "price": 67900, "km": 10436, "location": "Niort (79), Francia", "length_m": 7.36,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - camas gemelas + kit de relleno, automatica",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/adria-matrix-plus-670-dl/394781.html",
            "title": "Adria Matrix Plus 670 DL (2021) - la mas espaciosa, bano separado",
            "price": 62350, "km": 27893, "location": "Niort (79), Francia", "length_m": 7.49,
        },
        {
            "url": "https://www.caravan-wendt.de/de/fahrzeuge/carado-t-328-5-personenautomatikvoll-led-scheinwerfer-5f167.html",
            "title": "Carado T 328 (2026, ex-alquiler) - 5 plazas, bano separado, bajada de precio",
            "price": 69555, "km": 32000, "location": "Kremmin, Alemania", "length_m": 6.98,
        },
    ],
    "2026-07-27": [
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/etrusco-t-7400-sbc/394671.html",
            "title": "Etrusco T 7400 SBC (2023) - lider en relacion calidad-precio 4 semanas seguidas",
            "price": 58900, "km": 6500, "location": "Brens (81), Francia", "length_m": 7.40,
        },
        {
            "url": "https://massa-carrara.usato.it/mclouis-mc4-865-70267738",
            "title": "McLouis MC4 865 (2026) - 5 plazas confirmadas, la mas barata bien equipada",
            "price": 60900, "km": 12000, "location": "Pallerone, Italia", "length_m": 6.99,
        },
        {
            "url": "https://www.2dehands.be/v/caravans-en-kamperen/mobilhomes/m2423702399-dethleffs-just-go-7055-eb-155-pk-automaat",
            "title": "Dethleffs Just Go T 7055 EB (2023) - tercera semana sin cambios de precio",
            "price": 62950, "km": 29897, "location": "Best, Paises Bajos", "length_m": 7.36,
        },
        {
            "url": "https://www.annonces-caravaning.com/annonce-camping-car/sunlight-t-680-adventure-edition/384817.html",
            "title": "Sunlight T 680 Adventure Edition (2024) - mejor encaje familiar, sin cambios",
            "price": 67900, "km": 10436, "location": "Niort (79), Francia", "length_m": 7.36,
        },
        {
            "url": "https://www.milanuncios.com/autocaravanas-de-segunda-mano/autocaravana-perfilada-rapido-666f-cam-527648454.htm",
            "title": "Rapido 666F (2025) - primer concesionario espanol encontrado en 3 semanas",
            "price": 81471, "km": None, "location": "Irun, Gipuzkoa, Espana", "length_m": 7.49,
        },
    ],
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
        "km": raw.get("km"),
        "location": raw["location"],
        "photo": photo_cache[url],
        "specs": {"length_m": raw["length_m"]},
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
