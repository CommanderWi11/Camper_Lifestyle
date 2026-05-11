#!/usr/bin/env python3
"""Weekly camper-van search for Canary Islands listings."""

import json
import hashlib
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

PARAMS_FILE = Path(__file__).parent / "params.json"
LISTINGS_FILE = Path(__file__).parent.parent / "docs" / "listings.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

CANARY_KEYWORDS = {
    "canarias", "las palmas", "tenerife", "gran canaria",
    "la palma", "lanzarote", "fuerteventura", "la gomera",
    "el hierro", "la graciosa",
}


def load_params() -> dict:
    return json.loads(PARAMS_FILE.read_text())


def load_listings() -> list:
    if LISTINGS_FILE.exists():
        return json.loads(LISTINGS_FILE.read_text())
    return []


def save_listings(listings: list) -> None:
    LISTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LISTINGS_FILE.write_text(json.dumps(listings, ensure_ascii=False, indent=2))


def make_id(source: str, url: str) -> str:
    return f"{source}-{hashlib.md5(url.encode()).hexdigest()[:8]}"


def _parse_attrs(text: str) -> tuple[int | None, int | None]:
    """Parse year and km from Wallapop attribute string like '2008 · 80500 km · Diésel'."""
    year, km = None, None
    for part in text.split("·"):
        part = part.strip()
        if re.match(r"^\d{4}$", part):
            year = int(part)
        elif "km" in part.lower():
            km_str = re.sub(r"[^\d]", "", part)
            if km_str:
                km = int(km_str)
    return year, km


def fetch_wallapop(params: dict) -> list:
    """Scrape Wallapop search results using a headless browser (API is blocked)."""
    wp = params["wallapop"]
    results = []
    seen_ids: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for keyword in params["keywords"]:
            try:
                url = (
                    f"https://es.wallapop.com/search"
                    f"?keywords={quote(keyword)}"
                    f"&latitude={wp['latitude']}&longitude={wp['longitude']}"
                    f"&distance_in_km={wp['distance_km']}"
                    f"&max_sale_price={params['max_price']}"
                    f"&order_by=newest"
                )
                page.goto(url, timeout=30000)
                page.wait_for_timeout(4000)

                cards = page.query_selector_all('a[href*="/item/"][aria-label]')
                for card in cards:
                    href = card.get_attribute("href") or ""
                    title = card.get_attribute("aria-label") or ""

                    price_el = card.query_selector('strong[aria-label="Item price"]')
                    price_text = price_el.inner_text() if price_el else ""
                    price_str = re.sub(r"[^\d]", "", price_text)
                    try:
                        price = int(price_str)
                    except ValueError:
                        price = 0

                    attrs_el = card.query_selector("label")
                    year, km = _parse_attrs(attrs_el.inner_text() if attrs_el else "")

                    img_el = card.query_selector("img")
                    photo = img_el.get_attribute("src") if img_el else ""

                    full_url = f"https://es.wallapop.com{href}" if href.startswith("/") else href
                    listing_id = make_id("wallapop", full_url)
                    if listing_id in seen_ids:
                        continue
                    seen_ids.add(listing_id)

                    results.append({
                        "id": listing_id,
                        "title": title,
                        "price": price,
                        "year": year,
                        "km": km,
                        "sleeping": None,
                        "bathroom": None,
                        "location": "",
                        "source": "wallapop",
                        "url": full_url,
                        "photo": photo,
                        "status": "new",
                        "added_at": str(date.today()),
                    })
            except Exception as exc:
                print(f"[wallapop] error for '{keyword}': {exc}", file=sys.stderr)

        browser.close()

    return results


def fetch_milanuncios(params: dict) -> list:
    """Scrape Milanuncios autocaravanas category page, filter by Canary Islands.

    NOTE: If selectors break, inspect article[data-testid="AD_CARD"] on
    milanuncios.com/autocaravanas-de-segunda-mano/ and update below.
    """
    results = []

    try:
        url = "https://www.milanuncios.com/autocaravanas-de-segunda-mano/"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for article in soup.select('article[data-testid="AD_CARD"]'):
            title_el = article.select_one(".ma-AdCardV2-title")
            price_el = article.select_one(".ma-AdPrice-value")
            location_el = article.select_one(".ma-AdLocation-text")
            link_el = article.select_one("a.ma-AdCardListingV2-TitleLink")
            img_el = article.select_one("img.ma-AdCardV2-photo")

            if not title_el or not link_el:
                continue

            location = location_el.get_text(strip=True) if location_el else ""
            if not any(kw in location.lower() for kw in CANARY_KEYWORDS):
                continue

            price_str = (
                price_el.get_text(strip=True)
                .replace(".", "").replace(",", "").replace("€", "").replace("\xa0", "").strip()
            ) if price_el else "0"
            try:
                price = int(price_str)
            except ValueError:
                price = 0

            if params["max_price"] and price > params["max_price"]:
                continue

            href = link_el.get("href", "")
            full_url = f"https://www.milanuncios.com{href}" if href.startswith("/") else href

            results.append({
                "id": make_id("milanuncios", full_url),
                "title": title_el.get_text(strip=True),
                "price": price,
                "year": None,
                "km": None,
                "sleeping": None,
                "bathroom": None,
                "location": location,
                "source": "milanuncios",
                "url": full_url,
                "photo": img_el.get("src", "") if img_el else "",
                "status": "new",
                "added_at": str(date.today()),
            })
    except Exception as exc:
        print(f"[milanuncios] error: {exc}", file=sys.stderr)

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
