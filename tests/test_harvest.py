"""Harvester tests.

A note on what is deliberately NOT tested here: the Idealista scraper drives a real
browser session over an already-authenticated Chrome CDP connection (see the project
CLAUDE.md's "Idealista access" section) — there is no meaningful way to unit test
that without hitting the live, DataDome-protected site. Fake coverage is worse than
none, so it isn't attempted here.

What is covered is the part that actually decides what the family sees: the
fingerprint, same_house(), and the blocklist. Those are pure, fast, and worth
pinning down.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import harvest


# --------------------------------------------------------------------- identity

def test_make_id_is_stable_for_the_same_url():
    a = harvest.make_id("idealista", "https://example.com/item/1")
    b = harvest.make_id("idealista", "https://example.com/item/1")
    assert a == b
    assert a.startswith("idealista-")


def test_make_id_differs_by_url():
    assert harvest.make_id("idealista", "https://x.com/1") != harvest.make_id("idealista", "https://x.com/2")


def test_make_id_differs_by_source():
    url = "https://x.com/1"
    assert harvest.make_id("idealista", url) != harvest.make_id("fotocasa", url)


# ------------------------------------------------------------------ fingerprint

def test_fingerprint_matches_the_same_house_across_two_sources():
    """The point of the fingerprint: discard it once, it stays discarded everywhere.

    The same house listed on Idealista and rediscovered on Fotocasa has different
    URLs, hence different ids. The portal's SEO noise ("EN VENTA EN TAFIRA ALTA")
    must not make them look like two different houses.
    """
    idealista = {"title": "CHALET INDEPENDIENTE CON JARDIN PRIVADO EN VENTA EN TAFIRA ALTA"}
    fotocasa = {"title": "Chalet independiente jardín privado Tafira Alta"}
    assert harvest.fingerprint(idealista) == harvest.fingerprint(fotocasa)


def test_fingerprint_separates_different_addresses():
    a = {"title": "Chalet en Tafira, Calle Drago 12, jardín privado"}
    b = {"title": "Chalet en Tafira, Calle Laurisilva 8, jardín privado"}
    assert harvest.fingerprint(a) != harvest.fingerprint(b)


def test_fingerprint_ignores_price_so_a_discount_cannot_resurrect_a_reject():
    a = {"title": "Chalet en Tafira, Calle Drago 12, jardín privado", "price": 480000}
    b = {"title": "Chalet en Tafira, Calle Drago 12, jardín privado", "price": 410000}
    assert harvest.fingerprint(a) == harvest.fingerprint(b)


def test_fingerprint_splits_letters_from_digits_in_reference_codes():
    """A real-shape bug: one portal writes a plot reference as '34521 VC', another
    writes '34521VC' with no space — one token in one title, two in the other.
    Without splitting, the fingerprints (and therefore the board dedup) never
    matched and the same house showed up as two separate cards."""
    a = {"title": "Chalet en Tafira, Ref. 34521 VC, jardín privado"}
    b = {"title": "Chalet en Tafira Ref 34521VC jardín privado"}
    assert "34521" in harvest._slug_tokens(a["title"])
    assert "vc" in harvest._slug_tokens(a["title"])
    assert "34521" in harvest._slug_tokens(b["title"])
    assert "vc" in harvest._slug_tokens(b["title"])


# -------------------------------------------------------------------- same_house

def test_same_house_matches_a_cross_source_duplicate():
    """The kind of duplicate same_house() exists to catch: same house, same
    description, different portals, different wording."""
    idealista = {"source": "idealista",
                 "title": "Chalet independiente en Tafira con jardín privado, 4 dormitorios, garaje amplio"}
    fotocasa = {"source": "fotocasa",
                "title": "Casa independiente en Tafira con jardín privado, 4 habitaciones, garaje amplio"}
    assert harvest.same_house(idealista, fotocasa)


def test_same_house_respects_conflicting_construction_years():
    """Even with high title-token overlap, a conflicting construction year means
    these are two different houses, not the same one relisted."""
    a = {"source": "idealista", "year": 1998,
         "title": "Chalet independiente en Tafira con jardín privado, 4 dormitorios, garaje amplio"}
    b = {"source": "fotocasa", "year": 2015,
         "title": "Casa independiente en Tafira con jardín privado, 4 habitaciones, garaje amplio"}
    assert not harvest.same_house(a, b)


def test_same_house_requires_different_sources():
    """A developer's own listings page can legitimately carry two units of the
    identical model in a new-build development — that is real stock, not a
    scraping duplicate, so same-source near-identical titles must never merge."""
    a = {"source": "idealista", "title": "Chalet pareado Residencial Tafira Verde (Unidad 12)"}
    b = {"source": "idealista", "title": "Chalet pareado Residencial Tafira Verde (Unidad 14)"}
    assert not harvest.same_house(a, b)


def test_same_house_rejects_a_shared_neighborhood_as_a_false_positive():
    """Two totally different houses that merely share the same neighborhood name
    must not be treated as the same property just because the neighborhood word
    survives the stopword filter — real token overlap needs 3+ shared words,
    not one shared place name."""
    a = {"source": "idealista",
         "title": "Chalet en Tafira Alta con piscina, cerca del colegio, 5 dormitorios"}
    b = {"source": "fotocasa",
         "title": "Chalet en Tafira Alta con vistas al mar, junto al parque, 3 dormitorios"}
    assert not harvest.same_house(a, b)


def test_same_house_requires_real_token_overlap():
    a = {"source": "idealista", "title": "Villa moderna en Tafira con piscina privada"}
    b = {"source": "fotocasa", "title": "Piso reformado en Vegueta cerca del centro"}
    assert not harvest.same_house(a, b)


# -------------------------------------------------------------------- blocklist

def test_merge_candidates_drops_blocked_ids():
    new = [{"id": "a", "title": "Chalet en Tafira", "price": 1, "photo": ""},
           {"id": "b", "title": "Villa en Tafira", "price": 1, "photo": ""}]
    pool = harvest.merge_candidates([], new, blocked_ids={"a"}, blocked_fps=set())
    assert [c["id"] for c in pool] == ["b"]


def test_merge_candidates_drops_a_blocked_house_relisted_at_a_new_url():
    """The discard must survive the listing being deleted and re-posted."""
    rejected = {"id": "old", "title": "Chalet en Tafira con jardín privado",
                "price": 480000, "photo": ""}
    relisted = {"id": "brand-new-id", "title": "Chalet en Tafira con jardín privado",
                "price": 460000, "photo": ""}
    pool = harvest.merge_candidates([], [relisted], blocked_ids=set(),
                                    blocked_fps={harvest.fingerprint(rejected)})
    assert pool == []


def test_merge_candidates_purges_a_listing_discarded_since_the_last_run():
    existing = [{"id": "a", "title": "Chalet en Tafira", "price": 1,
                 "photo": "", "fingerprint": "chalet|tafira"}]
    assert harvest.merge_candidates(existing, [], blocked_ids={"a"}, blocked_fps=set()) == []


def test_merge_candidates_does_not_duplicate_an_already_known_listing():
    existing = [{"id": "a", "title": "Chalet en Tafira", "price": 480000,
                 "photo": "p.jpg", "fingerprint": "chalet|tafira"}]
    again = [{"id": "a", "title": "Chalet en Tafira", "price": 460000, "photo": ""}]
    pool = harvest.merge_candidates(existing, again, blocked_ids=set(), blocked_fps=set())
    assert len(pool) == 1
    assert pool[0]["price"] == 460000, "a price drop should refresh the existing entry"
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
