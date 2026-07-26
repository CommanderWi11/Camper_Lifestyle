#!/usr/bin/env python3
"""Stage A of the weekly pipeline: harvest Spain/Canary Islands motorhome candidates.

This script is deliberately DUMB. It casts a wide net and writes every plausible
candidate it finds to candidates.json — no body-type filtering (see the note above
_BRAND_RE). It does not rank, score, or pick winners — that is Stage B (`claude -p`,
driven by research-prompt.md), which reads the detail pages and judges against the
family's actual brief.

All sources below are hard-locked to Spain/the Canaries at the URL/param level, not
just by keyword — this script cannot reach Germany/France/Italy/Netherlands etc.
Europe-wide coverage (the current rubric's actual scope) happens live in Stage B via
WebSearch/WebFetch. Adding dedicated scrapers for the highest-value European portals
is a planned future phase, not done here.

Sources are tiered by how stable their contract is:

  Tier 1 — JSON APIs (rock solid, survive a site redesign)
    * Autocaravanas DM    — Shopify  /products.json
    * Mundo Autocaravanas — WooCommerce Store API /wp-json/wc/store/products

  Tier 2 — semantic CSS (stable-ish; a source dropping to 0 is logged loudly)
    * Wallapop, Milanuncios, Coches.net (Playwright — bot-protected, need a real browser)
    * Campermax, caravanas.net (static HTML)

  Tier 3 — hostile markup, deliberately NOT scraped here (see research-prompt.md)
    * RentCamper Canarias — a Wix site with obfuscated, auto-generated class names
      (`apPOZK`, `RuqxDs`) and no JSON-LD, so a CSS scraper would rot fast. It is
      also our single best family source ("literas ideal para niños", "4 plazas").
    * Autocaravanas Canarias — static HTML exposes exactly one vehicle; the rest of
      the fleet is JS-rendered or price-on-request.
    Stage B fetches both with WebFetch and reads the rendered text, which does not
    care what the class names are and self-heals when the sites change.

Discarded listings (the 🗑 button -> Supabase `camper_hidden`) are excluded here,
so a discard means "never searched again", not merely "hidden in the UI".
"""

import json
import hashlib
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

PARAMS_FILE = Path(__file__).parent / "params.json"
CANDIDATES_FILE = Path(__file__).parent / "candidates.json"
BLOCKLIST_FILE = Path(__file__).parent / "blocklist.json"
STARRED_FILE = Path(__file__).parent / "starred.json"
LISTINGS_FILE = Path(__file__).parent.parent / "docs" / "listings.json"
CONFIG_JS = Path(__file__).parent.parent / "docs" / "config.js"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    # NO Accept-Encoding. Advertising `br` makes servers return Brotli, which
    # requests cannot decode without the optional brotli package — you get binary
    # garbage instead of HTML/JSON, and every parser downstream fails silently.
    # Letting urllib3 negotiate (gzip/deflate) is correct and safe.
}

JSON_HEADERS = {**HEADERS, "Accept": "application/json"}

CANARY_KEYWORDS = {
    "canarias", "las palmas", "tenerife", "gran canaria",
    "la palma", "lanzarote", "fuerteventura", "la gomera",
    "el hierro", "la graciosa",
}

# 2026-07-26: the family's brief has NO body-type restriction (no "integral/
# perfilada only", no excluding capuchinas/campervans) — that was specific to the
# old Canary-only rubric this project used before. Body type is judged (if at all)
# by Stage B against the actual brief, not filtered here. Kept only as a recall
# signal for open-keyword sources (see _BRAND_RE / _is_target strict mode below),
# never as an exclusion.
#
# Brand list matches the brief's own "model families worth checking" (§5) exactly
# — not a broader "premium manufacturer" whitelist.
_BRAND_RE = re.compile(
    r"\b(adria(?:\s+(?:matrix|coral))?|hymer|b[uü]rstner|rapido|chausson|challenger|"
    r"weinsberg|knaus|carado|sunlight|dethleffs|benimar|elnagh|roller\s+team|"
    r"etrusco)\b",
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


def _load_json(path: Path) -> list:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"[warn] {path.name} is not valid JSON, treating as empty", file=sys.stderr)
    return []


def load_listings() -> list:
    return _load_json(LISTINGS_FILE)


def load_candidates() -> list:
    return _load_json(CANDIDATES_FILE)


def save_candidates(candidates: list) -> None:
    CANDIDATES_FILE.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))


def make_id(source: str, url: str) -> str:
    return f"{source}-{hashlib.md5(url.encode()).hexdigest()[:8]}"


def fetch_og_image(url: str) -> str:
    """Best-effort thumbnail for a detail page, via its Open Graph / Twitter card.

    Search cards often carry a lazy-load placeholder in <img src>, so a harvested
    listing can reach the board with no photo (coches.net does this). Every real
    listing page, though, declares an `og:image` for social sharing — that is the
    canonical hero shot. Used by Stage C to backfill winners with an empty photo,
    so the board never shows a bare placeholder for a vehicle that has a picture.
    Returns "" on any failure; the caller keeps its existing (empty) value.
    """
    if not url or not url.startswith("http"):
        return ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:  # network, HTTP, parse — all non-fatal here
        print(f"[og:image] {url} -> {exc}", file=sys.stderr)
        return ""
    for attrs in (
        {"property": "og:image"},
        {"name": "og:image"},
        {"property": "og:image:secure_url"},
        {"name": "twitter:image"},
        {"name": "twitter:image:src"},
    ):
        tag = soup.find("meta", attrs=attrs)
        content = (tag.get("content") if tag else "") or ""
        if content.startswith("http"):
            return content.strip()
    return ""


# Words that carry no identifying signal — they appear in almost every Canary
# dealer's SEO-stuffed title ("AUTOCARAVANA SEGUNDA MANO EN CANARIAS TENERIFE").
_FP_STOPWORDS = {
    "autocaravana", "autocaravanas", "caravana", "caravanas", "camper", "motorhome",
    "segunda", "mano", "ocasion", "venta", "vende", "vendo", "en", "de", "del", "la",
    "el", "los", "las", "y", "con", "por", "para", "canarias", "canaria", "gran",
    "tenerife", "palmas", "lanzarote", "fuerteventura", "palma", "gomera", "hierro",
    "islas", "nueva", "nuevo", "km", "plazas", "ref", "oferta", "oportunidad",
    # Body type is a property of the van, not part of its identity. One source
    # writes "Benimar Tessoro 496", another "Benimar Tessoro 496 perfilada" — the
    # same vehicle, and a discard on one must carry to the other.
    "perfilada", "perfilado", "perfiladas", "perfilados", "integral", "integrales",
    "capuchina", "capuchinas",
    # Base chassis — nearly every European integral/perfilada is built on one of
    # these, so the chassis brand is noise, not identity (the coachbuilder brand
    # + model is). Also engine/trim codes and sale-status words, equally generic.
    "fiat", "ducato", "ford", "transit", "iveco", "daily", "mercedes", "mercedesbenz",
    "sprinter", "peugeot", "boxer", "citroen", "jumper", "renault", "master",
    "vw", "volkswagen", "crafter",
    "td", "jtd", "tdi", "hdi", "dci", "cdti", "multijet", "cv",
    "reservada", "reservado", "oportunidad",
    # 2026-07-26: the Europe-wide brief's titles all describe the same shared
    # layout vocabulary (twin beds, separate shower, brand new) — a real
    # collision surfaced these as a false-positive same_vehicle match between a
    # Giottiline and an unrelated Challenger that merely shared "camas",
    # "gemelas", "estrenar". These describe the van's configuration, not its
    # identity, same reasoning as the body-type words above.
    "camas", "cama", "gemelas", "gemelo", "individuales", "traseras", "trasera",
    "delantera", "delanteras", "basculante", "convertible", "convertibles",
    "fija", "fijas", "fijo", "fijos", "dobles", "doble", "litera", "literas",
    "garaje", "ducha", "bano", "separado", "separada", "separados", "separadas",
    "combinado", "combinada", "kit", "relleno", "incluido", "opcional",
    "estrenar", "homologadas", "homologada", "plaza", "viajar", "dormir",
    "izquierda", "izquierdo", "volante",
}


def _slug_tokens(text: str) -> list[str]:
    """Lowercase, strip accents, drop stopwords/noise — leaving brand+model tokens.

    Letters and digits are split into separate tokens ("7400SB" -> "7400", "sb")
    so the same model matches regardless of whether a source's title happens to
    put a space in the model code ("7400 SB") or not.
    """
    norm = unicodedata.normalize("NFKD", text or "")
    norm = "".join(c for c in norm if not unicodedata.combining(c)).lower()
    tokens = re.findall(r"[a-z]+|[0-9]+", norm)
    return [t for t in tokens if t not in _FP_STOPWORDS and len(t) > 1]


def fingerprint(listing: dict) -> str:
    """Stable cross-source identity for the *same physical vehicle*.

    `id` is md5(url), so the same van listed on Wallapop and on the dealer's own
    site gets two different ids — and discarding one would not blocklist the other.
    The fingerprint is brand+model tokens + year, which survives the URL change.

    Price is deliberately excluded: sellers drop it, and a price cut must not
    resurrect a vehicle the family already rejected.

    This stays a strict, exact-match identity — used for blocklist propagation,
    where a false match would silently re-suppress an unrelated van. For "is this
    a duplicate CARD on the board", see the looser `same_vehicle()` below: two
    real listings of the same van rarely share every descriptive word (one site's
    "camas gemelas fijas" vs another's "garaje grande"), so exact-set equality
    under-catches there.
    """
    tokens = sorted(set(_slug_tokens(listing.get("title", ""))))
    year = listing.get("year") or ""
    return f"{'-'.join(tokens)}|{year}"


def same_vehicle(a: dict, b: dict) -> bool:
    """True if two listings from DIFFERENT sources are almost certainly the same
    physical vehicle relisted (e.g. the dealer's own site AND a marketplace).

    Deliberately cross-source only: a dealer's own catalog can legitimately carry
    two units of the identical model (a same-source near-duplicate is the
    dealer's data, not our scraper's problem to collapse), so same-source pairs
    are never merged no matter how similar their titles are. Cross-source plus a
    real token overlap (>=3 shared brand/model tokens, calibrated against a real
    false-positive-heavy dataset of shared-chassis titles) is what actually tells
    "same van seen twice" apart from "two different vans that happen to share a
    chassis and engine code".
    """
    src_a, src_b = a.get("source"), b.get("source")
    if not src_a or not src_b or src_a == src_b:
        return False
    overlap = set(_slug_tokens(a.get("title", ""))) & set(_slug_tokens(b.get("title", "")))
    if len(overlap) < 3:
        return False
    year_a, year_b = a.get("year"), b.get("year")
    if year_a and year_b and year_a != year_b:
        return False
    return True


def _supabase_config() -> tuple[str, str] | None:
    """Pull the Supabase URL + anon key straight out of docs/config.js.

    The dashboard already ships these to every visitor, so there is no new secret
    here — reading them from the same file keeps one source of truth.
    """
    if not CONFIG_JS.exists():
        return None
    text = CONFIG_JS.read_text()
    url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', text)
    key = re.search(r'SUPABASE_ANON_KEY\s*=\s*"([^"]+)"', text)
    if not (url and key):
        return None
    return url.group(1), key.group(1)


def _supabase_blocklist() -> set[str]:
    """Discarded ids from Supabase `camper_hidden`, or empty if it is unreachable."""
    cfg = _supabase_config()
    if not cfg:
        return set()
    url, key = cfg
    try:
        resp = requests.get(
            f"{url}/rest/v1/camper_hidden",
            params={"select": "listing_id"},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        resp.raise_for_status()
        return {row["listing_id"] for row in resp.json() if row.get("listing_id")}
    except Exception as exc:
        # Fail OPEN, loudly. A dead Supabase must not abort the weekly run, but a
        # silent failure that quietly resurrects rejected vans is worse than noise.
        print(f"[blocklist] Supabase unreachable ({type(exc).__name__}) — "
              f"falling back to {BLOCKLIST_FILE.name} only", file=sys.stderr)
        return set()


def load_blocklist() -> set[str]:
    """Every listing id the family has discarded, from both stores.

    Two stores on purpose:
      * Supabase `camper_hidden` — what the 🗑 button writes; syncs across devices.
      * scripts/blocklist.json  — committed to the repo; works with no backend at
        all, survives a Supabase outage, and is reviewable in a diff.

    The union wins, so a discard recorded in either place sticks.
    """
    local = set(_load_json(BLOCKLIST_FILE))
    remote = _supabase_blocklist()
    ids = local | remote
    print(f"[blocklist] {len(ids)} discarded "
          f"({len(remote)} from Supabase, {len(local)} from {BLOCKLIST_FILE.name})")
    return ids


def blocked_fingerprints(blocked_ids: set[str]) -> set[str]:
    """Fingerprints of every discarded vehicle, resolved from what we've already seen.

    Lets a discard on one source also suppress the same van relisted elsewhere.
    """
    known = load_candidates() + load_listings()
    return {fingerprint(l) for l in known if l.get("id") in blocked_ids}


def _supabase_starred() -> dict[str, str] | None:
    """Starred ids -> `created_at` from Supabase `camper_stars`, or None if unreachable.

    None (not {}) on failure, so the caller can fall back to the last-known-good
    local cache instead of silently wiping the Favorites section on a Supabase outage.
    """
    cfg = _supabase_config()
    if not cfg:
        return None
    url, key = cfg
    try:
        resp = requests.get(
            f"{url}/rest/v1/camper_stars",
            params={"select": "listing_id,created_at"},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        resp.raise_for_status()
        return {row["listing_id"]: row.get("created_at")
                for row in resp.json() if row.get("listing_id")}
    except Exception as exc:
        print(f"[starred] Supabase unreachable ({type(exc).__name__}) — "
              f"falling back to last cached {STARRED_FILE.name}", file=sys.stderr)
        return None


def load_starred() -> dict[str, str]:
    """Every listing id the family has starred, mapped to when they starred it.

    Unlike the blocklist there is no committed manual fallback here — a dead
    Supabase project must not silently drop everyone's Favorites on the next board
    update, so on failure we fall back to the last successful cache instead of {}.
    """
    remote = _supabase_starred()
    if remote is not None:
        STARRED_FILE.write_text(json.dumps(remote, indent=2, ensure_ascii=False))
        print(f"[starred] {len(remote)} starred (from Supabase, cached to {STARRED_FILE.name})")
        return remote

    cached = {}
    if STARRED_FILE.exists():
        try:
            cached = json.loads(STARRED_FILE.read_text())
        except Exception:
            cached = {}
    print(f"[starred] using last cached {STARRED_FILE.name} ({len(cached)} starred)")
    return cached


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
    """Return True if title looks like a candidate worth harvesting.

    No body-type filtering here (see the note above _BRAND_RE) — the brief cares
    about function (twin beds, LHD, weight, length, belts), not body type, and
    Stage B judges that from the detail page, not the search-result title.

    strict=True: for open-keyword searches (Wallapop) where the keyword match
    alone doesn't guarantee relevance — require a recognized brand as a weak
    relevance signal.
    strict=False: the source's own search/category already scoped results to
    motorhomes (Milanuncios, Coches.net, Autocasion, etc.) — accept everything.
    """
    if not strict:
        return True
    return bool(_BRAND_RE.search(title))
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

                    # coches.net lazy-loads: the visible <img src> is a 1x1/blur
                    # placeholder until scrolled into view, and the real URL sits in
                    # data-src / srcset. Take the first thing that looks like a real
                    # image; Stage C backfills via og:image if all of these are empty.
                    img_el = card.query_selector("img")
                    photo = ""
                    if img_el:
                        for attr in ("data-src", "src"):
                            val = img_el.get_attribute(attr) or ""
                            if val.startswith("http") and "data:image" not in val:
                                photo = val
                                break
                        if not photo:
                            srcset = img_el.get_attribute("srcset") or ""
                            first = srcset.split(",")[0].strip().split(" ")[0]
                            if first.startswith("http"):
                                photo = first

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


# ---------------------------------------------------------------------------
# Tier 1 — JSON APIs. These have a real contract and survive a site redesign.
# ---------------------------------------------------------------------------

def _blank(source: str, url: str, title: str) -> dict:
    """A candidate with every field the board expects, so downstream never KeyErrors."""
    return {
        "id": make_id(source, url),
        "title": title,
        "price": 0,
        "year": None,
        "km": None,
        "sleeping": None,
        "bathroom": None,
        "location": "",
        "source": source,
        "url": url,
        "photo": "",
        "status": "new",
        "added_at": str(date.today()),
    }


def fetch_autocaravanas_dm(params: dict) -> list:
    """Autocaravanas DM (Tenerife) — Shopify storefront.

    Shopify exposes every product as JSON at /products.json. No HTML parsing,
    nothing to break. Body type is NOT reliable from the title (their titles are
    SEO soup, and their tags list `INTEGRAL` and `CAPUCHINA` on the same vehicle),
    so we let it through here and let Stage B classify from the detail page.
    """
    results = []
    try:
        resp = requests.get("https://autocaravanasdm.com/products.json",
                            params={"limit": 250}, headers=JSON_HEADERS, timeout=30)
        resp.raise_for_status()
        for p in resp.json().get("products", []):
            if (p.get("product_type") or "").upper() not in ("AUTOCARAVANAS", ""):
                continue
            title = (p.get("title") or "").strip()
            if not title or not _is_target(title, strict=False):
                continue
            url = f"https://autocaravanasdm.com/products/{p['handle']}"
            item = _blank("autocaravanas_dm", url, title)
            variants = p.get("variants") or []
            if variants:
                try:
                    item["price"] = int(float(variants[0].get("price") or 0))
                except (TypeError, ValueError):
                    pass
            images = p.get("images") or []
            if images:
                item["photo"] = images[0].get("src", "")
            blob = f"{title} {BeautifulSoup(p.get('body_html') or '', 'html.parser').get_text(' ')}"
            item["year"] = _extract_year(blob)
            item["location"] = "Canarias"
            results.append(item)
    except Exception as exc:
        print(f"[autocaravanas_dm] error: {exc}", file=sys.stderr)
    return results


def fetch_mundo_autocaravanas(params: dict) -> list:
    """Mundo Autocaravanas (Tenerife) — WooCommerce Store API.

    /wp-json/wc/store/products returns clean JSON. Prices come in MINOR units
    (3450000 + currency_minor_unit=2 -> 34,500 EUR). They also sell plain cars,
    so drop anything in the `coches` category.
    """
    results = []
    try:
        resp = requests.get("https://mundoautocaravanas.com/wp-json/wc/store/products",
                            params={"per_page": 100}, headers=JSON_HEADERS, timeout=30)
        resp.raise_for_status()
        for p in resp.json():
            cats = {(c.get("slug") or "").lower() for c in (p.get("categories") or [])}
            # They also sell plain cars, and the catalogue keeps sold stock around.
            # Only "disponibles" is actually buyable today.
            if "coches" in cats or "disponibles" not in cats:
                continue
            title = BeautifulSoup(p.get("name") or "", "html.parser").get_text(" ", strip=True)
            if not title or not _is_target(title, strict=False):
                continue
            url = p.get("permalink") or ""
            if not url:
                continue
            item = _blank("mundo_autocaravanas", url, title)
            prices = p.get("prices") or {}
            try:
                minor = int(prices.get("currency_minor_unit", 2))
                item["price"] = int(int(prices.get("price") or 0) / (10 ** minor))
            except (TypeError, ValueError):
                pass
            images = p.get("images") or []
            if images:
                item["photo"] = images[0].get("src", "")
            desc = BeautifulSoup(p.get("description") or "", "html.parser").get_text(" ")
            item["year"] = _extract_year(f"{title} {desc}")
            item["location"] = "Tenerife"
            results.append(item)
    except Exception as exc:
        print(f"[mundo_autocaravanas] error: {exc}", file=sys.stderr)
    return results


# ---------------------------------------------------------------------------
# Tier 2 — static HTML with semantic class names.
# ---------------------------------------------------------------------------

def _soup(url: str) -> BeautifulSoup | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        print(f"[fetch] {url} -> {exc}", file=sys.stderr)
        return None


_PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+)\s*€|€\s*(\d{1,3}(?:[.\s]\d{3})+)")


def _price_from(text: str) -> int:
    m = _PRICE_RE.search(text or "")
    if not m:
        return 0
    raw = m.group(1) or m.group(2) or ""
    try:
        return int(re.sub(r"[^\d]", "", raw))
    except ValueError:
        return 0


def _ancestor_text(el, levels: int = 4) -> str:
    """Walk up from a link to the block that actually holds its price/specs."""
    node = el
    for _ in range(levels):
        if node.parent is None:
            break
        node = node.parent
        text = node.get_text(" ", strip=True)
        if "€" in text:
            return text
    return el.get_text(" ", strip=True)


def fetch_campermax(params: dict) -> list:
    """Campermax (Las Palmas). Bootstrap cards; card text carries price/year/km."""
    results = []
    seen = set()
    for page in range(1, 4):
        url = ("https://campermax.es/listing-category/en-venta/" if page == 1
               else f"https://campermax.es/listing-category/en-venta/page/{page}/")
        soup = _soup(url)
        if not soup:
            break
        cards = soup.select("div.card")
        found = 0
        for card in cards:
            link = card.select_one('a[href*="/listing/"]')
            if not link:
                continue
            href = link["href"]
            if href in seen:
                continue
            title_el = card.select_one("h3.finder-hp-listing-title") or link
            title = title_el.get_text(" ", strip=True)
            if not title or not _is_target(title, strict=False):
                continue
            text = card.get_text(" ", strip=True)
            seen.add(href)
            found += 1
            item = _blank("campermax", href, title)
            item["price"] = _price_from(text)
            item["year"] = _extract_year(text)
            km = re.search(r"([\d.]+)\s*km", text, re.IGNORECASE)
            if km:
                try:
                    item["km"] = int(re.sub(r"[^\d]", "", km.group(1)))
                except ValueError:
                    pass
            img = card.select_one("img")
            if img:
                item["photo"] = img.get("src") or img.get("data-src") or ""
            item["location"] = "Las Palmas"
            results.append(item)
        if found == 0:
            break
    return results


def fetch_caravanas_net(params: dict) -> list:
    """caravanas.net — private sellers.

    Their province filter ONLY works as a URL path. `?provincia=` is silently
    ignored and returns all ~138 national listings, so never use the query form.
    """
    results = []
    seen = set()
    for province in ("las-palmas", "santa-cruz-de-tenerife"):
        soup = _soup(f"https://www.caravanas.net/search/autocaravana/{province}")
        if not soup:
            continue
        for link in soup.select('a[href*="/ad/"]'):
            href = link.get("href") or ""
            m = re.search(r"/ad/(\d+)/([\w-]+)", href)
            if not m or href in seen:
                continue
            slug = m.group(2)
            title = link.get_text(" ", strip=True) or slug.replace("-", " ").title()
            if not _is_target(title, strict=False):
                continue
            seen.add(href)
            full = href if href.startswith("http") else f"https://www.caravanas.net{href}"
            item = _blank("caravanas_net", full, title)
            block = _ancestor_text(link, levels=5)
            item["price"] = _price_from(block)
            item["year"] = _extract_year(block)
            img = link.select_one("img")
            if img:
                item["photo"] = img.get("src") or img.get("data-src") or ""
            item["location"] = province.replace("-", " ").title()
            results.append(item)
    return results


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def apply_price_filter(items: list, params: dict) -> list:
    """Drop anything outside the budget. Price 0 means 'not published' — keep it,
    Stage B will read the real price off the detail page."""
    lo, hi = params.get("min_price", 0), params.get("max_price", 10 ** 9)
    return [i for i in items if not i["price"] or lo <= i["price"] <= hi]


def merge_candidates(existing: list, new_results: list,
                     blocked_ids: set[str], blocked_fps: set[str]) -> list:
    """Grow the candidate pool, never resurrecting a discarded vehicle.

    The pool is the dedupe ledger: it remembers everything we have ever seen so a
    vehicle is not re-announced as 'new' every single week.
    """
    by_id = {item["id"]: item for item in existing}
    added = skipped = 0
    for item in new_results:
        if item["id"] in blocked_ids or fingerprint(item) in blocked_fps:
            skipped += 1
            continue
        if item["id"] in by_id:
            # Refresh the volatile fields; keep first_seen semantics via added_at.
            prev = by_id[item["id"]]
            prev["price"] = item["price"] or prev["price"]
            prev["photo"] = item["photo"] or prev["photo"]
            continue
        item["fingerprint"] = fingerprint(item)
        by_id[item["id"]] = item
        added += 1
    # Purge anything discarded since the last run.
    kept = [i for i in by_id.values()
            if i["id"] not in blocked_ids and i.get("fingerprint", fingerprint(i)) not in blocked_fps]
    purged = len(by_id) - len(kept)
    print(f"[pool] +{added} new, {skipped} blocked at harvest, {purged} purged, {len(kept)} total")
    return kept


SOURCES = [
    ("wallapop", fetch_wallapop),
    ("milanuncios", fetch_milanuncios),
    ("coches_net", fetch_coches_net),
    ("autocaravanas_dm", fetch_autocaravanas_dm),
    ("mundo_autocaravanas", fetch_mundo_autocaravanas),
    ("campermax", fetch_campermax),
    ("caravanas_net", fetch_caravanas_net),
]


def main() -> None:
    params = load_params()
    blocked_ids = load_blocklist()
    blocked_fps = blocked_fingerprints(blocked_ids)
    if blocked_fps:
        print(f"[blocklist] {len(blocked_fps)} vehicle fingerprints blocked cross-source")

    harvested: list = []
    for name, fetcher in SOURCES:
        print(f"Fetching {name}...")
        try:
            found = apply_price_filter(fetcher(params), params)
        except Exception as exc:
            print(f"[{name}] FAILED: {exc}", file=sys.stderr)
            found = []
        # A source silently dropping to zero is how these pipelines rot. Say so.
        marker = "  <-- ZERO, check selectors" if not found else ""
        print(f"[{name}] {len(found)} candidates{marker}")
        harvested.extend(found)

    pool = merge_candidates(load_candidates(), harvested, blocked_ids, blocked_fps)
    save_candidates(pool)
    print(f"Wrote {len(pool)} candidates to {CANDIDATES_FILE.name}")


if __name__ == "__main__":
    main()
