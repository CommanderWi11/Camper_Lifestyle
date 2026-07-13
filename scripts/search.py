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

# Accept only integrales and perfiladas. Reject vans, capuchinas, and obvious car listings.
_ACCEPT_RE = re.compile(r"\b(integral|integrales|perfilad[ao]s?)\b", re.IGNORECASE)
_REJECT_RE = re.compile(
    r"\b(camper|campervan|furgoneta|capuchina|sobrecabina|alcoba|"
    r"vito|vivaro|trafic|california|caravelle|multivan|marco\s+polo)\b",
    re.IGNORECASE,
)
# Premium integral/perfilada manufacturers — any of these in a title is an accept signal.
_BRAND_RE = re.compile(
    r"\b(hymer|b[uü]rstner|carthago|concorde|frankia|niesmann|morelo|"
    r"benimar|chausson|adria\s+matrix|sun\s+living|pilote|rapido|"
    r"dethleffs|roller\s+team|mclouis|laika)\b",
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


def _is_target(title: str, strict: bool = True) -> bool:
    """Return True if title looks like an integral or perfilada motorhome.

    strict=True: title must mention integral/perfilada OR a known premium brand.
    strict=False: any title that doesn't match the reject list passes — use for sources
    already filtered to the autocaravanas category (Milanuncios, Coches.net, Autocasion).
    """
    if _REJECT_RE.search(title):
        return False
    if strict:
        return bool(_ACCEPT_RE.search(title) or _BRAND_RE.search(title))
    return True


def _extract_year(text: str) -> int | None:
    """Find the first plausible 4-digit vehicle year in a free-text blob."""
    if not text:
        return None
    # Prefer explicit "Año: YYYY" label when present.
    m = re.search(r"a[nñ]o\s*:?\s*(\d{4})", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Fallback: any 4-digit year in [1990, current+1].
    cap = date.today().year + 1
    for m in re.finditer(r"\b(19[9]\d|20\d\d)\b", text):
        y = int(m.group(1))
        if 1990 <= y <= cap:
            return y
    return None


def _passes_age(year: int | None, max_age_years: int) -> bool:
    """Return True if year is unknown or if (current_year - year) <= max_age_years."""
    if year is None or not max_age_years:
        return True
    return (date.today().year - year) <= max_age_years


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
    max_age = params.get("max_age_years", 0)
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

                    # Wallapop is a keyword-search source spanning all categories.
                    # Strict mode keeps recall high via _BRAND_RE while filtering out
                    # cars, real estate, and other non-motorhome listings.
                    if not _is_target(title, strict=True):
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
                    if not _passes_age(year, max_age):
                        continue

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
    """Scrape Milanuncios autocaravanas/Canarias listings via Playwright.

    Uses the geo-filtered URL (/canarias.htm) so we don't need a location post-filter.
    Playwright is required because most cards are JS-rendered; plain requests only
    sees the 3 "destacado" cards.

    If selectors break, inspect article[data-testid="AD_CARD"] on
    milanuncios.com/autocaravanas-de-segunda-mano/canarias.htm and update below.
    """
    min_price = params.get("min_price", 0)
    max_weight = params.get("max_weight_kg", 99999)
    max_age = params.get("max_age_years", 0)
    results = []

    url = "https://www.milanuncios.com/autocaravanas-de-segunda-mano/canarias.htm"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                locale="es-ES",
                user_agent=HEADERS["User-Agent"],
            )
            page = ctx.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)
            # Scroll once to trigger lazy-loaded cards lower in the list.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            cards = page.query_selector_all('article[data-testid="AD_CARD"]')
            print(f"[milanuncios] found {len(cards)} raw cards", file=sys.stderr)

            for card in cards:
                title_el = card.query_selector(".ma-AdCardV2-title")
                price_el = card.query_selector(".ma-AdPrice-value")
                location_el = card.query_selector(".ma-AdLocation-text")
                link_el = card.query_selector("a.ma-AdCardListingV2-TitleLink")
                img_el = card.query_selector("img.ma-AdCardV2-photo") or card.query_selector("img")

                if not title_el or not link_el:
                    continue

                title = title_el.inner_text().strip()
                if not _is_target(title, strict=False):
                    continue
                if not _passes_weight(title, max_weight):
                    continue

                price_str = (
                    price_el.inner_text().strip()
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

                href = link_el.get_attribute("href") or ""
                full_url = f"https://www.milanuncios.com{href}" if href.startswith("/") else href
                location = location_el.inner_text().strip() if location_el else ""

                year = _extract_year(card.inner_text())
                if not _passes_age(year, max_age):
                    continue

                results.append({
                    "id": make_id("milanuncios", full_url),
                    "title": title,
                    "price": price,
                    "year": year,
                    "km": None,
                    "sleeping": None,
                    "bathroom": None,
                    "location": location,
                    "source": "milanuncios",
                    "url": full_url,
                    "photo": img_el.get_attribute("src") if img_el else "",
                    "status": "new",
                    "added_at": str(date.today()),
                })
            browser.close()
    except Exception as exc:
        print(f"[milanuncios] error: {exc}", file=sys.stderr)

    return results


def _humanlike_context(p):
    """Return a Playwright context tuned to look less like a headless bot.

    Used for sources with bot-detection (Coches.net) that return "Ups!" or
    block the listing UI when the request looks automated.
    """
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    ctx = browser.new_context(
        locale="es-ES",
        timezone_id="Atlantic/Canary",
        user_agent=HEADERS["User-Agent"],
        viewport={"width": 1440, "height": 900},
    )
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, ctx


def fetch_coches_net(params: dict) -> list:
    """Scrape coches.net autocaravanas/Canarias listings via Playwright.

    Bot-detection on coches.net is aggressive: requests that look headless get
    served an "Ups! Parece que algo no va bien..." stub page with zero cards.
    We use a humanlike browser context (locale, timezone, viewport, UA hint
    spoofing) which reliably yields 6-22 cards per first-page load.

    Pagination via ?page=N is unreliable (typically returns 0 on page 2 even
    when the total count is higher), so we only scrape page 1.

    If selectors break, inspect div.mt-CardAd on
    coches.net/autocaravanas-segunda-mano/canarias/ and update below.
    """
    min_price = params.get("min_price", 0)
    max_price = params.get("max_price", 99999999)
    max_weight = params.get("max_weight_kg", 99999)
    max_age = params.get("max_age_years", 0)
    results = []

    url = "https://www.coches.net/autocaravanas-segunda-mano/canarias/?page=1"

    try:
        with sync_playwright() as p:
            browser, ctx = _humanlike_context(p)
            page = ctx.new_page()
            page.goto(url, timeout=45000)
            page.wait_for_timeout(7000)
            # One scroll to nudge any lazy-loaded cards into view.
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

            # Detect the bot-block stub page and bail cleanly.
            if "algo no va bien" in page.content().lower():
                print("[coches_net] bot-block detected, returning empty", file=sys.stderr)
                browser.close()
                return []

            cards = page.query_selector_all('div.mt-CardAd')
            print(f"[coches_net] found {len(cards)} raw cards", file=sys.stderr)

            for card in cards:
                try:
                    link_el = card.query_selector('a[href*="-arvo.aspx"]')
                    if not link_el:
                        continue
                    href = link_el.get_attribute("href") or ""
                    full_url = (
                        f"https://www.coches.net{href}" if href.startswith("/") else href
                    )

                    text = card.inner_text()
                    title_el = card.query_selector('h2.mt-CardAd-infoHeaderTitle a') or link_el
                    title = title_el.inner_text().strip()
                    if not title:
                        continue
                    if not _is_target(title, strict=False):
                        continue
                    if not _passes_weight(text, max_weight):
                        continue

                    # Price: first "NN.NNN €" or "N.NNN €" in card text.
                    price = 0
                    m = re.search(r"(\d{1,3}(?:\.\d{3})+)\s*€", text)
                    if m:
                        price = int(m.group(1).replace(".", ""))
                    if price and price < min_price:
                        continue
                    if price and price > max_price:
                        continue

                    year = _extract_year(text)
                    if not _passes_age(year, max_age):
                        continue

                    # Km: "NN.NNN km" or "N.NNN km".
                    km = None
                    m = re.search(r"(\d{1,3}(?:\.\d{3})+)\s*km", text, re.IGNORECASE)
                    if m:
                        km = int(m.group(1).replace(".", ""))

                    # Location: any line containing a Canary keyword.
                    location = ""
                    for line in text.split("\n"):
                        if any(kw in line.lower() for kw in CANARY_KEYWORDS):
                            location = line.strip()
                            break

                    img_el = card.query_selector("img")
                    photo = img_el.get_attribute("src") if img_el else ""

                    results.append({
                        "id": make_id("coches_net", full_url),
                        "title": title,
                        "price": price,
                        "year": year,
                        "km": km,
                        "sleeping": None,
                        "bathroom": None,
                        "location": location,
                        "source": "coches_net",
                        "url": full_url,
                        "photo": photo,
                        "status": "new",
                        "added_at": str(date.today()),
                    })
                except Exception as exc:
                    print(f"[coches_net] error parsing card: {exc}", file=sys.stderr)
            browser.close()
    except Exception as exc:
        print(f"[coches_net] error: {exc}", file=sys.stderr)

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

    print("Fetching Coches.net...")
    coches = fetch_coches_net(params)
    print(f"[coches_net] {len(coches)} listings after filters")

    merged = merge_listings(existing, wallapop + milanuncios + coches)
    save_listings(merged)
    print("Done.")


if __name__ == "__main__":
    main()
