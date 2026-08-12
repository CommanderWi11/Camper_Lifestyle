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


def test_fingerprint_splits_letters_from_digits_in_model_codes():
    """A real bug: coches.net wrote '7400 SB', milanuncios wrote '7400SB' — one
    token in one title, two in the other. Without splitting, the fingerprints
    (and therefore the board dedup) never matched and the same van showed up as
    two separate cards."""
    a = {"title": "Etrusco T 7400 SB, viajan y duermen 5"}
    b = {"title": "Etrusco 7400SB 130cv"}
    assert "7400" in harvest._slug_tokens(a["title"])
    assert "sb" in harvest._slug_tokens(a["title"])
    assert "7400" in harvest._slug_tokens(b["title"])
    assert "sb" in harvest._slug_tokens(b["title"])


# -------------------------------------------------------------------- same_vehicle

def test_same_vehicle_matches_the_real_etrusco_duplicate():
    """The actual duplicate found live on the board 2026-07-20: same van, same
    model code, different sites, different description wording."""
    coches_net = {"source": "coches_net",
                  "title": "Etrusco T 7400 SB — perfilada, viajan y duermen 5, garaje grande"}
    milanuncios = {"source": "milanuncios",
                   "title": "Etrusco 7400SB — integral, camas gemelas traseras fijas + basculante"}
    assert harvest.same_vehicle(coches_net, milanuncios)


def test_same_vehicle_requires_different_sources():
    """A dealer's own catalog can legitimately carry two units of the identical
    model — that is real stock, not a scraping duplicate, so same-source near-
    identical titles must never be merged."""
    a = {"source": "mundo_autocaravanas", "title": "MCLOUIS TANDY PLUS 640 (Ref. 1548)"}
    b = {"source": "mundo_autocaravanas", "title": "MCLOUIS TANDY PLUS 640 (Ref. 1325)"}
    assert not harvest.same_vehicle(a, b)


def test_same_vehicle_rejects_shared_chassis_as_a_false_positive():
    """Two totally different coachbuilder models that merely share a Fiat Ducato
    base chassis and diesel engine code must not be treated as the same van —
    this was the dominant false-positive source before chassis/engine words were
    added to the stopword list."""
    a = {"source": "mundo_autocaravanas", "title": "Fiat Ducato 2.8 JTD – ADRIA CORAL 660 SP G – ¡Reservada!"}
    b = {"source": "autocaravanas_dm", "title": "Fiat Ducato 2.8 JTD – ELNAGH JOXY 10- ¡Reservada!"}
    assert not harvest.same_vehicle(a, b)


def test_same_vehicle_requires_real_token_overlap():
    a = {"source": "wallapop", "title": "Hymer B-Klasse ModernComfort I 580"}
    b = {"source": "milanuncios", "title": "Chausson Titanium 720"}
    assert not harvest.same_vehicle(a, b)


def test_same_vehicle_respects_conflicting_years():
    a = {"source": "coches_net", "title": "Etrusco T 7400 SB, viajan y duermen 5", "year": 2015}
    b = {"source": "milanuncios", "title": "Etrusco 7400SB 130cv, viajan y duermen 5", "year": 2019}
    assert not harvest.same_vehicle(a, b)


# -------------------------------------------------------------------- filtering
#
# 2026-07-26: the redesign to use only the family's brief removed every Stage-A
# exclusionary gate except weight — no body-type filter, no age cutoff, no price
# floor/ceiling. None of those had any basis in the brief (which explicitly says
# never discard on mileage/age alone, and treats budget as a target Stage B
# weighs, not a hard reject), and age/price gates actively contradicted it. The
# brand-whitelist "strict" accept mode (`_is_target`/`_BRAND_RE`) was also removed
# — it only existed to support Wallapop's open-keyword search, which isn't in the
# brief's portal list and was dropped along with Autocaravanas DM, Mundo
# Autocaravanas, Campermax, and caravanas.net (also not in the brief).

def test_passes_weight_rejects_over_the_b_licence_limit():
    assert not harvest._passes_weight("Integral 4.5 t", 3500)
    assert harvest._passes_weight("Perfilada MMA: 3500 kg", 3500)
    assert harvest._passes_weight("no weight mentioned", 3500)


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


def test_fetch_og_image_reads_the_open_graph_tag():
    resp = MagicMock(status_code=200)
    resp.text = ('<html><head>'
                 '<meta property="og:image" content="https://cdn/hero.jpg"/>'
                 '</head></html>')
    with patch("harvest.requests.get", return_value=resp):
        assert harvest.fetch_og_image("https://site/ad") == "https://cdn/hero.jpg"


def test_fetch_og_image_falls_back_to_twitter_card():
    resp = MagicMock(status_code=200)
    resp.text = ('<html><head>'
                 '<meta name="twitter:image" content="https://cdn/tw.jpg"/>'
                 '</head></html>')
    with patch("harvest.requests.get", return_value=resp):
        assert harvest.fetch_og_image("https://site/ad") == "https://cdn/tw.jpg"


def test_fetch_og_image_ignores_non_http_and_missing_tags():
    resp = MagicMock(status_code=200)
    resp.text = '<html><head><meta property="og:image" content="/relative.jpg"/></head></html>'
    with patch("harvest.requests.get", return_value=resp):
        assert harvest.fetch_og_image("https://site/ad") == ""


def test_fetch_og_image_is_best_effort_and_swallows_errors():
    assert harvest.fetch_og_image("") == ""
    assert harvest.fetch_og_image("not-a-url") == ""
    with patch("harvest.requests.get", side_effect=OSError("network down")):
        assert harvest.fetch_og_image("https://site/ad") == ""


def test_scrape_urls_are_nationwide_spain_not_canarias_filtered():
    """2026-08-11: scope restored to Europe-wide; Stage A's two deterministic
    scrapers cover nationwide Spain again, not the Canarias-filtered URLs from
    the 2026-07-30 detour."""
    import inspect
    mila_src = inspect.getsource(harvest.fetch_milanuncios)
    coches_src = inspect.getsource(harvest.fetch_coches_net)
    assert "canarias.htm" not in mila_src
    assert "https://www.milanuncios.com/autocaravanas-de-segunda-mano/\"" in mila_src
    assert "/canarias/" not in coches_src
    assert "https://www.coches.net/autocaravanas-y-remolques/?page=1\"" in coches_src
