#!/usr/bin/env python3
"""Weekly camper-van search for Canary Islands listings."""

import json
import hashlib
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

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
    LISTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
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
                    "category_ids": "100",
                },
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("search_objects", []):
                slug = item.get("web_slug", "")
                if not slug:
                    continue
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
    the selectors below.
    """
    results = []

    for keyword in params["keywords"][:2]:  # limit to avoid rate limiting
        try:
            url = (
                f"https://www.milanuncios.com/autocaravanas-y-campers/"
                f"?texto={quote(keyword)}"
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
