"""Harvester tests.

A note on what is deliberately NOT tested here: the Playwright fetchers (Wallapop,
Milanuncios, Coches.net) drive a real headless browser. The previous version of this
file "tested" them by patching `search.requests.get` — which those fetchers stopped
calling when they moved to Playwright. The patches were no-ops, so those tests either
hit the live network or asserted nothing at all. Fake coverage is worse than none, so
they are gone.

What is covered is the part that actually decides what the family sees: the filters,
the fingerprint, and the blocklist. Those are pure, fast, and worth pinning down.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import harvest


# --------------------------------------------------------------------- identity

def test_make_id_is_stable_for_the_same_url():
    a = harvest.make_id("wallapop", "https://example.com/item/1")
    b = harvest.make_id("wallapop", "https://example.com/item/1")
    assert a == b
    assert a.startswith("wallapop-")


def test_make_id_differs_by_url():
    assert harvest.make_id("wallapop", "https://x.com/1") != harvest.make_id("wallapop", "https://x.com/2")


def test_make_id_differs_by_source():
    url = "https://x.com/1"
    assert harvest.make_id("wallapop", url) != harvest.make_id("milanuncios", url)


# ------------------------------------------------------------------ fingerprint

def test_fingerprint_matches_the_same_van_across_two_sources():
    """The point of the fingerprint: discard it once, it stays discarded everywhere.

    The same vehicle listed by a dealer and on Wallapop has different URLs, hence
    different ids. The dealer's SEO noise ("AUTOCARAVANA SEGUNDA MANO EN CANARIAS")
    must not make them look like two different vans.
    """
    dealer = {"title": "AUTOCARAVANA SEGUNDA MANO BENIMAR TESSORO 496 EN CANARIAS", "year": 2020}
    wallapop = {"title": "Benimar Tessoro 496 perfilada", "year": 2020}
    assert harvest.fingerprint(dealer) == harvest.fingerprint(wallapop)


def test_fingerprint_separates_different_model_years():
    a = {"title": "Benimar Tessoro 496", "year": 2020}
    b = {"title": "Benimar Tessoro 496", "year": 2016}
    assert harvest.fingerprint(a) != harvest.fingerprint(b)


def test_fingerprint_ignores_price_so_a_discount_cannot_resurrect_a_reject():
    a = {"title": "Benimar Tessoro 496", "year": 2020, "price": 58000}
    b = {"title": "Benimar Tessoro 496", "year": 2020, "price": 51000}
    assert harvest.fingerprint(a) == harvest.fingerprint(b)


# -------------------------------------------------------------------- filtering

def test_is_target_accepts_integrales_and_perfiladas():
    assert harvest._is_target("Autocaravana perfilada Benimar", strict=True)
    assert harvest._is_target("HYMER integral 2019", strict=True)


def test_is_target_rejects_vans_and_capuchinas():
    assert not harvest._is_target("Camper van Mercedes Vito", strict=True)
    assert not harvest._is_target("Autocaravana capuchina Elnagh", strict=False)
    assert not harvest._is_target("Furgoneta camperizada", strict=False)


def test_is_target_accepts_a_premium_brand_without_the_body_keyword():
    # Wallapop titles rarely say "perfilada"; the brand name is the accept signal.
    assert harvest._is_target("Carthago c-tourer 2018", strict=True)


def test_passes_age_is_lenient_when_the_year_is_unknown():
    # Milanuncios almost never publishes a year. Dropping those would gut recall,
    # so an unknown year passes and Stage B resolves it from the detail page.
    assert harvest._passes_age(None, 10)


def test_passes_weight_rejects_over_the_b_licence_limit():
    assert not harvest._passes_weight("Integral 4.5 t", 3500)
    assert harvest._passes_weight("Perfilada MMA: 3500 kg", 3500)
    assert harvest._passes_weight("no weight mentioned", 3500)


def test_price_parsing_handles_spanish_thousands_separators():
    assert harvest._price_from("Precio 64.900 €") == 64900
    assert harvest._price_from("€64.900") == 64900
    assert harvest._price_from("sin precio") == 0


def test_price_filter_keeps_listings_with_no_published_price():
    """Price 0 means 'precio a consultar'. Stage B reads the real price off the
    detail page — dropping them here would silently lose most dealer stock."""
    params = {"min_price": 20000, "max_price": 100000}
    items = [{"price": 0}, {"price": 50000}, {"price": 5000}, {"price": 200000}]
    assert harvest.apply_price_filter(items, params) == [{"price": 0}, {"price": 50000}]


# -------------------------------------------------------------------- blocklist

def test_merge_candidates_drops_blocked_ids():
    new = [{"id": "a", "title": "Benimar", "price": 1, "photo": "", "year": None},
           {"id": "b", "title": "Hymer", "price": 1, "photo": "", "year": None}]
    pool = harvest.merge_candidates([], new, blocked_ids={"a"}, blocked_fps=set())
    assert [c["id"] for c in pool] == ["b"]


def test_merge_candidates_drops_a_blocked_vehicle_relisted_at_a_new_url():
    """The discard must survive the seller deleting the ad and re-posting it."""
    rejected = {"id": "old", "title": "Benimar Tessoro 496", "year": 2020,
                "price": 58000, "photo": ""}
    relisted = {"id": "brand-new-id", "title": "Benimar Tessoro 496", "year": 2020,
                "price": 55000, "photo": ""}
    pool = harvest.merge_candidates([], [relisted], blocked_ids=set(),
                                    blocked_fps={harvest.fingerprint(rejected)})
    assert pool == []


def test_merge_candidates_purges_a_listing_discarded_since_the_last_run():
    existing = [{"id": "a", "title": "Benimar", "year": None, "price": 1,
                 "photo": "", "fingerprint": "benimar|"}]
    assert harvest.merge_candidates(existing, [], blocked_ids={"a"}, blocked_fps=set()) == []


def test_merge_candidates_does_not_duplicate_an_already_known_listing():
    existing = [{"id": "a", "title": "Benimar", "year": None, "price": 50000,
                 "photo": "p.jpg", "fingerprint": "benimar|"}]
    again = [{"id": "a", "title": "Benimar", "year": None, "price": 48000, "photo": ""}]
    pool = harvest.merge_candidates(existing, again, blocked_ids=set(), blocked_fps=set())
    assert len(pool) == 1
    assert pool[0]["price"] == 48000, "a price drop should refresh the existing entry"
    assert pool[0]["photo"] == "p.jpg", "an empty new photo must not wipe the old one"


def test_blocklist_falls_open_when_supabase_is_unreachable():
    """Supabase being down must not abort the run — but local discards still count."""
    with patch("harvest._supabase_config", return_value=("https://dead.invalid", "key")), \
         patch("harvest.requests.get", side_effect=OSError("dns failure")), \
         patch("harvest._load_json", return_value=["locally-discarded"]):
        assert harvest.load_blocklist() == {"locally-discarded"}


# ----------------------------------------------------------------- JSON sources

def test_shopify_fetcher_parses_products_json():
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"products": [{
        "title": "RIMOR SUPERBRIG 675 AUTOCARAVANA PERFILADA",
        "handle": "rimor-superbrig-675",
        "product_type": "AUTOCARAVANAS",
        "variants": [{"price": "42900.00"}],
        "images": [{"src": "https://cdn/img.jpg"}],
        "body_html": "<p>Año: 2010</p>",
    }]}
    with patch("harvest.requests.get", return_value=resp):
        got = harvest.fetch_autocaravanas_dm({})
    assert len(got) == 1
    assert got[0]["price"] == 42900
    assert got[0]["year"] == 2010
    assert got[0]["url"] == "https://autocaravanasdm.com/products/rimor-superbrig-675"


def test_woo_fetcher_converts_minor_units_and_skips_cars():
    resp = MagicMock(status_code=200)
    resp.json.return_value = [
        {"name": "ROLLER TEAM ZEFIRO perfilada", "permalink": "https://m.com/p/1",
         "prices": {"price": "5990000", "currency_minor_unit": 2},
         "categories": [{"slug": "disponibles"}], "images": [{"src": "i.jpg"}]},
        {"name": "CITROEN BERLINGO", "permalink": "https://m.com/p/2",
         "prices": {"price": "1300000", "currency_minor_unit": 2},
         "categories": [{"slug": "coches"}, {"slug": "disponibles"}], "images": []},
    ]
    with patch("harvest.requests.get", return_value=resp):
        got = harvest.fetch_mundo_autocaravanas({})
    assert len(got) == 1, "the car must be dropped"
    assert got[0]["price"] == 59900, "5,990,000 minor units == 59,900 EUR"


def test_a_source_that_throws_does_not_kill_the_harvest():
    with patch("harvest.requests.get", side_effect=OSError("network down")):
        assert harvest.fetch_autocaravanas_dm({}) == []
        assert harvest.fetch_mundo_autocaravanas({}) == []
