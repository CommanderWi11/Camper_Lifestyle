#!/usr/bin/env python3
"""Stage A of the daily pipeline: harvest Idealista.es house-listing candidates.

This script is deliberately DUMB. It casts a wide net over Idealista's
venta-viviendas search for Tafira / Las Palmas de Gran Canaria and writes every
plausible candidate it finds to candidates.json. It does not rank, score, or pick
winners — that is Stage B (`claude -p`, driven by research-prompt.md), which reads
the detail pages and judges every candidate against the family's actual brief
(budget <=EUR500k, >=3 bedrooms, private garden, home-office space).

2026-08-26: repurposed from the Motorhome_Search project's two-source Playwright
scraper (Milanuncios + Coches.net) to a single-source Idealista scraper for this
project's house search. Idealista's DataDome protection is aggressive, so this
connects to an already-authenticated Chrome session over CDP (see
`_connect_idealista_browser`) rather than launching a fresh headless context —
mirroring the working pattern in the sibling project `Assets_HQ/BSA_Options`.

Discarded listings (the trash-can button -> Supabase `house_hidden`) are excluded
here, so a discard means "never searched again", not merely "hidden in the UI".
"""

import json
import hashlib
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

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
    listing can reach the board with no photo. Every real listing page, though,
    declares an `og:image` for social sharing — that is the canonical hero shot.
    Used by Stage C to backfill winners with an empty photo, so the board never
    shows a bare placeholder for a house that has a picture.
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


# Words that carry no identifying signal — they appear in almost every Idealista
# listing title ("Piso en venta en Tafira Alta, reformado, con jardín y terraza").
_FP_STOPWORDS = {
    "piso", "pisos", "casa", "casas", "chalet", "chalets", "vivienda", "viviendas",
    "duplex", "atico", "aticos", "planta", "plantas",
    "dormitorio", "dormitorios", "habitacion", "habitaciones", "bano", "banos",
    "reformado", "reformada", "reformados", "reformadas", "obra", "nueva", "nuevo",
    "nuevos", "nuevas", "oportunidad", "oportunidades", "m2",
    "venta", "vende", "se", "garaje", "garajes", "jardin", "jardines",
    "terraza", "terrazas",
    # Generic connectors/articles — no identifying signal in any Spanish title.
    "con", "de", "del", "en", "para", "la", "el", "los", "las", "a", "y", "por",
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
    """Stable cross-source identity for the *same physical house*.

    `id` is md5(url), so the same house listed on two sites gets two different
    ids — and discarding one would not blocklist the other. The fingerprint is
    descriptive-title tokens + year (year is rarely present for houses and
    defaults to "", which is fine — the token set carries the real signal).

    Price is deliberately excluded: sellers drop it, and a price cut must not
    resurrect a house the family already rejected.

    This stays a strict, exact-match identity — used for blocklist propagation,
    where a false match would silently re-suppress an unrelated house. For "is
    this a duplicate CARD on the board", see the looser `same_house()` below: two
    real listings of the same house rarely share every descriptive word, so
    exact-set equality under-catches there.
    """
    tokens = sorted(set(_slug_tokens(listing.get("title", ""))))
    year = listing.get("year") or ""
    return f"{'-'.join(tokens)}|{year}"


def same_house(a: dict, b: dict) -> bool:
    """True if two listings from DIFFERENT sources are almost certainly the same
    physical house relisted (e.g. the agency's own site AND a marketplace).

    Deliberately cross-source only: an agency's own catalog can legitimately
    carry two similar units (a same-source near-duplicate is the agency's data,
    not our scraper's problem to collapse), so same-source pairs are never merged
    no matter how similar their titles are. Cross-source plus a real token
    overlap (>=3 shared descriptive tokens, calibrated the same way the original
    motorhome-search version of this function was) is what actually tells "same
    house seen twice" apart from "two different houses that happen to share
    generic listing vocabulary".
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
    """Discarded ids from Supabase `house_hidden`, or empty if it is unreachable."""
    cfg = _supabase_config()
    if not cfg:
        return set()
    url, key = cfg
    try:
        resp = requests.get(
            f"{url}/rest/v1/house_hidden",
            params={"select": "listing_id"},
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=20,
        )
        resp.raise_for_status()
        return {row["listing_id"] for row in resp.json() if row.get("listing_id")}
    except Exception as exc:
        # Fail OPEN, loudly. A dead Supabase must not abort the daily run, but a
        # silent failure that quietly resurrects a rejected house is worse than noise.
        print(f"[blocklist] Supabase unreachable ({type(exc).__name__}) — "
              f"falling back to {BLOCKLIST_FILE.name} only", file=sys.stderr)
        return set()


def load_blocklist() -> set[str]:
    """Every listing id the family has discarded, from both stores.

    Two stores on purpose:
      * Supabase `house_hidden` — what the trash-can button writes; syncs across
        devices.
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
    """Starred ids -> `created_at` from Supabase `house_stars`, or None if unreachable.

    None (not {}) on failure, so the caller can fall back to the last-known-good
    local cache instead of silently wiping the Favorites section on a Supabase outage.
    """
    cfg = _supabase_config()
    if not cfg:
        return None
    url, key = cfg
    try:
        resp = requests.get(
            f"{url}/rest/v1/house_stars",
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


def _extract_year(text: str) -> int | None:
    """Find the first plausible 4-digit year (e.g. construction year) in a free-text blob.

    Not currently called by `fetch_idealista` (search cards rarely surface a
    build year — that lives on the detail page, which is Stage B's job), but
    kept as a generic, reusable helper in case a future selector fix surfaces
    one on the card itself.
    """
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


# CDP endpoint for the dedicated, already-authenticated Idealista Chrome profile.
# See this project's CLAUDE.md -> "Idealista access (CDP session)" for the launch
# command (~/.chrome-home-quest-cdp, port 9223) and why 127.0.0.1 not localhost.
IDEALISTA_CDP_URL = "http://127.0.0.1:9223"

# LIVE-VERIFIED 2026-08-26 against idealista.com (logged-in CDP session) via the
# site's own location autocomplete — the originally-guessed
# ".../venta-viviendas/las-palmas-de-gran-canaria/tafira/" 404s; these are the
# real per-district "geo" URLs. Tafira Alta/Baja are the true target zone; the
# city-wide URL is the explicit fallback research-prompt.md asks for when Tafira
# alone is too thin (it is: ~1-2 matching listings on a given day) — Stage B
# decides `is_target_area` per listing from `location`, harvest.py just casts
# the net over all three.
IDEALISTA_SEARCH_AREAS = [
    ("Tafira Alta", "https://www.idealista.com/geo/venta-viviendas/tafira-alta-gran-canaria/"),
    ("Tafira Baja", "https://www.idealista.com/geo/venta-viviendas/tafira-baja-gran-canaria/"),
    ("Las Palmas de Gran Canaria (fallback)",
     "https://www.idealista.com/venta-viviendas/las-palmas-de-gran-canaria-las-palmas/"),
]

# LIVE-VERIFIED 2026-08-26: idealista's filter-URL router is picky — a lone
# amenity/room segment (e.g. "jardin/" or "de-tres-dormitorios-en-adelante/" by
# itself) 404s, and the "-en-adelante" ("or more") suffix guessed originally is
# wrong. The combo actually confirmed working (via Luis's own saved-search URL
# and direct navigation) is "con-precio-hasta_<N>,de-tres-dormitorios,jardin/",
# in that order. Only min_bedrooms=3 is confirmed; other counts are left
# unmapped (falls back to client-side-only filtering, which already exists as
# a safety net below) rather than guessing an unverified slug.
_BEDROOM_FILTER_SLUGS = {
    3: "de-tres-dormitorios",
}

# ---------------------------------------------------------------------------
# LIVE-VERIFIED 2026-08-26 against a real listing card on idealista.com
# (Chalet pareado, Tafira Alta). One correction from the original guess: there
# is no separate location element on a card — `.item-detail-char` is the
# amenity/room-count row (garage/bedrooms/m²), not a location. The address is
# only present inside the title, so location is now derived from it (see
# `_location_from_title`) instead of a second selector.
# ---------------------------------------------------------------------------
_CARD_SELECTOR = "article.item"
_TITLE_SELECTOR = "a.item-link"
_PRICE_SELECTOR = "span.item-price"
_DETAIL_SELECTOR = "span.item-detail"
_IMAGE_SELECTOR = "picture img, img"


def _location_from_title(title: str) -> str:
    """Idealista card titles are "<tipo> en <dirección>" (e.g. "Chalet pareado en
    CL Cantonera, 15, Tafira, Las Palmas de Gran Canaria") — there is no separate
    location element on the card (see comment above `_CARD_SELECTOR`). Splits off
    everything after the first " en " as the address; falls back to the full
    title if that marker isn't present rather than returning nothing.
    """
    parts = title.split(" en ", 1)
    return parts[1].strip() if len(parts) == 2 else title


def _build_idealista_search_url(base_url: str, params: dict) -> str:
    """Compose an Idealista search URL for one area, per the live-verified facet
    scheme (see module-level comment above `_BEDROOM_FILTER_SLUGS`). Garden is a
    fixed hard requirement of this project's brief (not parametrized in
    params.json like price/bedrooms are), so "jardin" is always appended.
    Results are also re-checked client-side in `fetch_idealista` against
    `params`, so an unmapped/no-op facet here degrades to "harvests too much"
    rather than "silently harvests the wrong thing".
    """
    filters = []
    max_price = params.get("max_price")
    if max_price:
        filters.append(f"con-precio-hasta_{int(max_price)}")
    min_bedrooms = params.get("min_bedrooms")
    if min_bedrooms:
        slug = _BEDROOM_FILTER_SLUGS.get(int(min_bedrooms))
        if slug:
            filters.append(slug)
        else:
            print(f"[idealista] no bedroom-filter slug mapped for "
                  f"min_bedrooms={min_bedrooms}; relying on client-side filtering only",
                  file=sys.stderr)
    filters.append("jardin")
    return base_url + ",".join(filters) + "/"


def _connect_idealista_browser(p):
    """Connect to the dedicated, already-authenticated Idealista Chrome profile.

    Reuses a real logged-in session (started manually via the command documented
    in this project's CLAUDE.md) instead of a fresh headless context — a fresh
    context gets blocked by DataDome outright, per the sibling project
    BSA_Options's documented experience. Fails loudly if that Chrome isn't
    running with the expected profile/port; never silently falls back to a
    headless launch.

    Returns (browser, page). The caller must NOT call `browser.close()` — that
    would close Luis's real, persistent Chrome window, not just this automation's
    tab. Do NOT close the `page` (tab) this function opens/reuses, even when
    done with it — if it's the profile's only open tab, closing it leaves the
    browser with zero contexts, which breaks the *next* `connect_over_cdp` call
    outright (live-verified 2026-08-26; see the comment in `fetch_idealista`'s
    finally block for the reproduction).
    """
    try:
        browser = p.chromium.connect_over_cdp(IDEALISTA_CDP_URL)
    except Exception as exc:
        raise RuntimeError(
            "Cannot connect to the Idealista CDP Chrome profile at "
            f"{IDEALISTA_CDP_URL} ({type(exc).__name__}: {exc}). Start it first:\n"
            "  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\\n"
            "    --remote-debugging-port=9223 \\\n"
            '    --user-data-dir="$HOME/.chrome-home-quest-cdp"\n'
            "then log into idealista.com manually in that window if the session "
            "has expired. This does not fall back to a fresh headless browser — "
            "that would just get blocked by DataDome."
        ) from exc

    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    return browser, page


def _parse_idealista_cards(page) -> list:
    """Parse every listing card on the current search-results page.

    Each card is parsed defensively: a card that doesn't match the expected
    shape is logged and skipped, not allowed to crash the whole harvest.
    """
    out = []
    cards = page.query_selector_all(_CARD_SELECTOR)
    print(f"[idealista] found {len(cards)} raw cards", file=sys.stderr)

    for card in cards:
        try:
            link_el = card.query_selector(_TITLE_SELECTOR)
            if not link_el:
                continue
            href = link_el.get_attribute("href") or ""
            if not href:
                continue
            full_url = f"https://www.idealista.com{href}" if href.startswith("/") else href

            title = (link_el.get_attribute("title") or link_el.inner_text() or "").strip()
            if not title:
                continue

            price_el = card.query_selector(_PRICE_SELECTOR)
            price_text = price_el.inner_text() if price_el else ""
            price = 0
            m = re.search(r"([\d.,]+)\s*€?", price_text)
            if m:
                try:
                    price = int(re.sub(r"[.,]", "", m.group(1)))
                except ValueError:
                    price = 0

            detail_text = " ".join(
                el.inner_text() for el in card.query_selector_all(_DETAIL_SELECTOR)
            )
            bedrooms = None
            m = re.search(r"(\d+)\s*hab", detail_text, re.IGNORECASE)
            if m:
                bedrooms = int(m.group(1))

            img_el = card.query_selector(_IMAGE_SELECTOR)
            photo = ""
            if img_el:
                for attr in ("src", "data-src"):
                    val = img_el.get_attribute(attr) or ""
                    if val.startswith("http"):
                        photo = val
                        break

            out.append({
                "id": make_id("idealista", full_url),
                "title": title,
                "price": price,
                "bedrooms": bedrooms,
                "year": _extract_year(detail_text),
                "location": _location_from_title(title),
                "source": "idealista",
                "url": full_url,
                "photo": photo,
                "status": "new",
                "added_at": str(date.today()),
            })
        except Exception as exc:
            print(f"[idealista] error parsing card: {exc}", file=sys.stderr)
    return out


def fetch_idealista(params: dict) -> list:
    """Scrape Idealista.es venta-viviendas listings across Tafira Alta, Tafira
    Baja, and — as the explicit fallback research-prompt.md asks for — the wider
    Las Palmas de Gran Canaria city (see `IDEALISTA_SEARCH_AREAS`). Tafira alone
    is thin (1-2 live matches on a given day), which is exactly why the fallback
    area exists; Stage B is what actually decides `is_target_area` per listing,
    from `location`, not this harvester.

    Connects via CDP to an already-authenticated Chrome session (see
    `_connect_idealista_browser`) rather than launching a fresh context, since
    Idealista's DataDome protection blocks headless/automated browsers outright.

    The search URL applies the live-verified price/bedroom/garden facets (see
    `_build_idealista_search_url`); results are also re-checked client-side
    against `params` below as a safety net for any area/count not covered by a
    known facet mapping.
    """
    min_bedrooms = int(params.get("min_bedrooms") or 0)
    max_price = params.get("max_price") or None
    min_price = params.get("min_price") or 0
    results = []

    with sync_playwright() as p:
        browser, page = _connect_idealista_browser(p)
        try:
            for label, base_url in IDEALISTA_SEARCH_AREAS:
                url = _build_idealista_search_url(base_url, params)
                try:
                    page.goto(url, timeout=45000)
                    page.wait_for_timeout(4000)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)

                    if "/login" in page.url:
                        print("[idealista] session expired — redirected to /login; "
                              "re-authenticate manually in the CDP Chrome window "
                              f"({IDEALISTA_CDP_URL})", file=sys.stderr)
                        break

                    print(f"[idealista] {label}: {url}", file=sys.stderr)
                    for item in _parse_idealista_cards(page):
                        price, bedrooms = item["price"], item["bedrooms"]
                        # Client-side re-check: an area/count not covered by a
                        # known facet mapping degrades to unfiltered, so don't
                        # trust the URL alone to have filtered.
                        if max_price and price and price > max_price:
                            continue
                        if min_price and price and price < min_price:
                            continue
                        if min_bedrooms and bedrooms is not None and bedrooms < min_bedrooms:
                            continue
                        results.append(item)
                except Exception as exc:
                    print(f"[idealista] error fetching {label}: {exc}", file=sys.stderr)
        finally:
            # Deliberately NOT closing `page` here, and never `browser.close()`.
            # LIVE-VERIFIED 2026-08-26: closing the tab this run drove used to
            # happen here — harmless-looking, but if it was the CDP profile's
            # ONLY open tab, the browser is left with zero tabs/contexts, and
            # Playwright's `connect_over_cdp` then fails outright on the *next*
            # run ("Browser.setDownloadBehavior: Browser context management is
            # not supported" — Playwright needs at least one existing context to
            # attach to). Reproduced for real: the first harvest run closed the
            # only tab, and the very next run couldn't connect at all. Leaving
            # the tab open costs nothing (it's reused as `ctx.pages[0]` next
            # time) and guarantees the profile always has a live context.
            pass

    return results


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def merge_candidates(existing: list, new_results: list,
                     blocked_ids: set[str], blocked_fps: set[str]) -> list:
    """Grow the candidate pool, never resurrecting a discarded house.

    The pool is the dedupe ledger: it remembers everything we have ever seen so a
    house is not re-announced as 'new' every single run.
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
    ("idealista", fetch_idealista),
]


def main() -> None:
    params = load_params()
    blocked_ids = load_blocklist()
    blocked_fps = blocked_fingerprints(blocked_ids)
    if blocked_fps:
        print(f"[blocklist] {len(blocked_fps)} house fingerprints blocked cross-source")

    harvested: list = []
    for name, fetcher in SOURCES:
        print(f"Fetching {name}...")
        try:
            found = fetcher(params)
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
