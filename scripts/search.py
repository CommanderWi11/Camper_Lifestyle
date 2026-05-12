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

# Titles containing these words indicate an integrated motorhome (not a van).
_MOTORHOME_RE = re.compile(
    r"\b(autocaravana|integral|capuchina|perfilada|perfilad|mobil home|motorhome)\b",
    re.IGNORECASE,
)

# Title must contain at least one of these to be considered a van/campervan.
_VAN_RE = re.compile(
    r"\b(camper|campervan|furgoneta|transporter|sprinter|ducato|transit|master|"
    r"jumper|boxer|crafter|vito|vivaro|trafic|t[3-7]|california|"
    r"caravelle|multivan|van)\b",
    re.IGNORECASE,
)

# Patterns that indicate weight is mentioned in the title/text.
_WEIGHT_RE = re.compile(
    r"(\d[\d.,]*)\s*(?:t\b|tn\b|ton\b)|"
    r"(?:MMA|MTM|PMA|PTMA)\s*:?\s*(\d{3,5})\s*(?:kg)?",
    re.IGNORECASE,
)


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
    """Parse year and km from an attribute string like '2008 · 80500 km · Diésel'."""
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


def _is_van(title: str) -> bool:
    """Return True if title looks like a campervan (not a car, not a full motorhome).

    Requires a positive match on known van/camper terms — a blocklist-only approach
    lets cars through when Wallapop fuzzy-matches their description keywords.
    """
    if _MOTORHOME_RE.search(title):
        return False
    return bool(_VAN_RE.search(title))


def _passes_weight(text: str, max_kg: int) -> bool:
    """Return True if no weight is found in text, or if found weight is within limit.

    Weight in tonnes is converted to kg (e.g. 3.5t → 3500 kg).
    Listings without any weight mention always pass through.
    """
    m = _WEIGHT_RE.search(text)
    if not m:
        return True
    tonnes_str, kg_str = m.group(1), m.group(2)
    if tonnes_str:
        weight_kg = int(float(tonnes_str.replace(",", ".")) * 1000)
    else:
        weight_kg = int(re.sub(r"[^\d]", "", kg_str))
    return weight_kg <= max_kg


def fetch_wallapop(params: dict) -> list:
    """Scrape Wallapop search results using a headless browser (API is blocked)."""
    wp = params["wallapop"]
    min_price = params.get("min_price", 0)
    max_weight = params.get("max_weight_kg", 99999)
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
                    f"&min_sale_price={min_price}"
                    f"&max_sale_price={params['max_price']}"
                    f"&order_by=newest"
                )
                page.goto(url, timeout=30000)
                page.wait_for_timeout(4000)

                cards = page.query_selector_all('a[href*="/item/"][aria-label]')
                for card in cards:
                    href = card.get_attribute("href") or ""
                    title = card.get_attribute("aria-label") or ""

                    if not _is_van(title):
                        continue
                    if not _passes_weight(title, max_weight):
                        continue

                    price_el = card.query_selector('strong[aria-label="Item price"]')
                    price_text = price_el.inner_text() if price_el else ""
                    price_str = re.sub(r"[^\d]", "", price_text)
                    try:
                        price = int(price_str)
                    except ValueError:
                        price = 0

                    if price and price < min_price:
                        continue

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
    min_price = params.get("min_price", 0)
    max_weight = params.get("max_weight_kg", 99999)
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

            title = title_el.get_text(strip=True)
            if not _is_van(title):
                continue
            if not _passes_weight(title, max_weight):
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
            if min_price and price and price < min_price:
                continue

            href = link_el.get("href", "")
            full_url = f"https://www.milanuncios.com{href}" if href.startswith("/") else href

            results.append({
                "id": make_id("milanuncios", full_url),
                "title": title,
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


def fetch_autoscout24(params: dict) -> list:
    """Scrape Autoscout24 camper listings for Spain (post-filtered to Canary Islands).

    AS24 is primarily a mainland-Europe platform — Canary Islands coverage may be sparse.
    Uses Playwright since AS24 blocks plain requests. If the URL structure changes,
    inspect https://www.autoscout24.es and update the search URL and selectors below.
    """
    min_price = params.get("min_price", 0)
    max_weight = params.get("max_weight_kg", 99999)
    results = []
    seen_ids: set[str] = set()

    search_url = (
        f"https://www.autoscout24.es/lst/"
        f"?atype=C"
        f"&pricefrom={min_price}"
        f"&priceto={params['max_price']}"
        f"&cy=E"
        f"&ustate=N,U"
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(search_url, timeout=30000)
            page.wait_for_timeout(4000)

            # AS24 renders listing cards as <article> tags.
            articles = page.query_selector_all('article[data-item-name="regular-ad"]')
            print(f"[autoscout24] found {len(articles)} raw cards", file=sys.stderr)

            for article in articles:
                try:
                    # Title
                    title_el = article.query_selector("h2")
                    title = title_el.inner_text().strip() if title_el else ""
                    if not title:
                        continue

                    if not _is_van(title):
                        continue
                    if not _passes_weight(title, max_weight):
                        continue

                    # URL
                    link_el = article.query_selector('a[href*="/annonce/"]')
                    if not link_el:
                        link_el = article.query_selector("a[href]")
                    href = link_el.get_attribute("href") if link_el else ""
                    full_url = (
                        f"https://www.autoscout24.es{href}"
                        if href.startswith("/") else href
                    )
                    if not full_url:
                        continue

                    listing_id = make_id("autoscout24", full_url)
                    if listing_id in seen_ids:
                        continue
                    seen_ids.add(listing_id)

                    # Price — try multiple selectors since class names change
                    price = 0
                    for price_sel in [
                        'p[data-testid="regular-ad-price"]',
                        'strong[class*="Price"]',
                        'span[class*="price"]',
                    ]:
                        price_el = article.query_selector(price_sel)
                        if price_el:
                            price_str = re.sub(r"[^\d]", "", price_el.inner_text())
                            price = int(price_str) if price_str else 0
                            break

                    if price and price < min_price:
                        continue
                    if price and price > params["max_price"]:
                        continue

                    # Location — post-filter to Canary Islands
                    location = ""
                    for loc_sel in [
                        'span[data-testid="regular-ad-seller-address"]',
                        'div[class*="seller"] span',
                        'address',
                    ]:
                        loc_el = article.query_selector(loc_sel)
                        if loc_el:
                            location = loc_el.inner_text().strip()
                            break

                    if location and not any(kw in location.lower() for kw in CANARY_KEYWORDS):
                        continue

                    # Year and km from vehicle details text
                    year, km = None, None
                    for detail_sel in [
                        'span[data-testid="vehicle-detail"]',
                        'ul[class*="DetailsSection"] li',
                        'dl',
                    ]:
                        detail_el = article.query_selector(detail_sel)
                        if detail_el:
                            year, km = _parse_attrs(detail_el.inner_text())
                            break

                    # Photo
                    img_el = article.query_selector("img")
                    photo = img_el.get_attribute("src") if img_el else ""

                    results.append({
                        "id": listing_id,
                        "title": title,
                        "price": price,
                        "year": year,
                        "km": km,
                        "sleeping": None,
                        "bathroom": None,
                        "location": location,
                        "source": "autoscout24",
                        "url": full_url,
                        "photo": photo,
                        "status": "new",
                        "added_at": str(date.today()),
                    })
                except Exception as exc:
                    print(f"[autoscout24] error parsing card: {exc}", file=sys.stderr)

            browser.close()
    except Exception as exc:
        print(f"[autoscout24] error: {exc}", file=sys.stderr)

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
    print(f"[wallapop] {len(wallapop)} listings after filters")

    print("Fetching Milanuncios...")
    milanuncios = fetch_milanuncios(params)
    print(f"[milanuncios] {len(milanuncios)} listings after filters")

    print("Fetching Autoscout24...")
    autoscout24 = fetch_autoscout24(params)
    print(f"[autoscout24] {len(autoscout24)} listings after filters")

    merged = merge_listings(existing, wallapop + milanuncios + autoscout24)
    save_listings(merged)
    print("Done.")


if __name__ == "__main__":
    main()
