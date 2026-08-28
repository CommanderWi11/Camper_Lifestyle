"""The gate between a language model and the family's live dashboard.

`claude -p` does the judging, and it is good at it — but it is still a model, and a
bad run must never reach docs/listings.json. Every one of these tests describes a way
a run could go wrong and asserts that we refuse to publish rather than corrupt the board.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apply_winners
from apply_winners import Invalid, validate


def ok(**over):
    w = {
        "id": "idealista-1a2b3c4d",
        "url": "https://www.idealista.com/inmueble/12345678/",
        "source": "idealista",
        "title": "Chalet con jardín en Tafira, 4 dormitorios",
        "price": 420000,
        "rank": 1,
        "score": 87,
        "verdict": "Parcela con jardín privado y despacho independiente confirmados.",
        "specs": {"bedrooms": 4, "has_garden": True},
    }
    w.update(over)
    return w


def test_a_good_run_validates():
    got = validate([ok()], blocked=set())
    assert got[0]["id"] == "idealista-1a2b3c4d"
    assert got[0]["flags"] == []
    assert got[0]["specs"] == {"bedrooms": 4, "has_garden": True}


def test_more_than_five_winners_is_refused():
    with pytest.raises(Invalid, match="at most 5"):
        validate([ok(id=f"x{i}", rank=i) for i in range(1, 7)], blocked=set())


def test_fewer_than_five_is_fine():
    """The Tafira market is small. Three good houses beats five with two duds."""
    got = validate([ok(id="a", rank=1), ok(id="b", rank=2), ok(id="c", rank=3)], blocked=set())
    assert len(got) == 3


def test_a_discarded_listing_is_dropped_not_fatal():
    """The whole point of the 🗑 button. research-prompt.md tells Stage B to check
    the discard list itself, but that's prompt-following, not a guarantee — one bad
    entry should cost a rank slot, not fail the whole run and leave the board
    untouched for a full retry."""
    got = validate([ok(id="rejected")], blocked={"rejected"})
    assert got == []


def test_a_relisted_discarded_house_is_dropped_via_same_house():
    """A discarded house can reappear under a *different* id entirely — relisted
    on another portal, or rediscovered by Stage B's live search. Id-only blocking
    would miss it, so this cross-checks same_house() (title/specs overlap) against
    every known blocked listing, not just exact id equality."""
    blocked_house = {
        "id": "idealista-de4813bc", "source": "idealista",
        "title": "Chalet independiente en Tafira con jardín privado, 4 dormitorios, garaje amplio",
    }
    relisted = ok(
        id="", source="fotocasa", rank=1,
        title="Casa independiente en Tafira con jardín privado, 4 habitaciones, garaje amplio",
    )
    with patch("apply_winners.blocked_listings", return_value=[blocked_house]):
        got = validate([relisted], blocked=set())
    assert got == []


def test_dropping_a_discarded_winner_renumbers_the_survivors():
    got = validate(
        [ok(id="a", rank=1), ok(id="rejected", rank=2), ok(id="c", rank=3)],
        blocked={"rejected"},
    )
    assert [w["id"] for w in got] == ["a", "c"]
    assert [w["rank"] for w in got] == [1, 2], "rank 3 must not survive as a gap"


def test_duplicate_ids_are_refused():
    with pytest.raises(Invalid, match="duplicate"):
        validate([ok(id="same", rank=1), ok(id="same", rank=2)], blocked=set())


def test_duplicate_ranks_are_refused():
    with pytest.raises(Invalid, match="rank assigned twice"):
        validate([ok(id="a", rank=1), ok(id="b", rank=1)], blocked=set())


def test_non_consecutive_ranks_are_refused():
    with pytest.raises(Invalid, match="not consecutive"):
        validate([ok(id="a", rank=1), ok(id="b", rank=4)], blocked=set())


def test_a_hallucinated_score_is_refused():
    with pytest.raises(Invalid, match="score"):
        validate([ok(score=150)], blocked=set())


def test_an_empty_verdict_is_refused():
    """A winner with no reasoning is not a research result, it's a guess."""
    with pytest.raises(Invalid, match="no real verdict"):
        validate([ok(verdict="Buena.")], blocked=set())


def test_a_missing_url_is_refused():
    with pytest.raises(Invalid, match="no usable url"):
        validate([ok(url="")], blocked=set())


def test_an_id_is_derived_when_claude_found_the_listing_itself():
    """Listings Claude discovers directly (e.g. live search on Fotocasa/pisos.com,
    not the deterministic Idealista harvester) have no harvested id — derive one
    the same way the harvester would, so stars and comments can attach to it."""
    got = validate(
        [ok(id="", source="fotocasa", url="https://www.fotocasa.es/es/comprar/vivienda/x")],
        blocked=set(),
    )
    assert got[0]["id"] == apply_winners.make_id("fotocasa", "https://www.fotocasa.es/es/comprar/vivienda/x")


def test_garbage_instead_of_a_list_is_refused():
    with pytest.raises(Invalid, match="expected a JSON list"):
        validate({"winners": []}, blocked=set())


def test_price_over_budget_is_refused():
    """Budget is a hard requirement (project CLAUDE.md) — a machine-checked
    invariant, not just prompt-trust."""
    with pytest.raises(Invalid, match="price"):
        validate([ok(price=520000)], blocked=set())


def test_fewer_than_three_bedrooms_is_refused():
    with pytest.raises(Invalid, match="bedroom"):
        validate([ok(specs={"bedrooms": 2, "has_garden": True})], blocked=set())


def test_gc_track_rejects_three_bedrooms_but_accepts_four():
    """The 'gc' track's hard gate is >=4 bedrooms, not >=3 — validate() takes
    the gate as a parameter (see tracks.py's min_bedrooms_gate) rather than a
    hardcoded literal, so this exercises that per-track wiring directly."""
    with pytest.raises(Invalid, match="bedroom"):
        validate([ok(specs={"bedrooms": 3, "has_garden": True})], blocked=set(), min_bedrooms=4)

    got = validate([ok(specs={"bedrooms": 4, "has_garden": True})], blocked=set(), min_bedrooms=4)
    assert got[0]["specs"]["bedrooms"] == 4


def test_no_private_garden_is_refused():
    with pytest.raises(Invalid, match="garden"):
        validate([ok(specs={"bedrooms": 4, "has_garden": False})], blocked=set())


def test_within_budget_with_garden_and_enough_bedrooms_passes():
    got = validate([ok()], blocked=set())
    assert got[0]["specs"]["has_garden"] is True


def test_the_same_house_ranked_twice_from_different_sources_is_refused():
    """If the research pass picks up the same house from two different portals as
    two separate 'winners', that is a research bug, not two real properties —
    refuse to publish rather than show the family a duplicate card."""
    idealista = ok(id="idealista-abc", rank=1, source="idealista",
                    title="Chalet independiente en Tafira con jardín privado, 4 dormitorios, garaje amplio")
    fotocasa = ok(id="fotocasa-xyz", rank=2, source="fotocasa",
                   title="Casa independiente en Tafira con jardín privado, 4 habitaciones, garaje amplio")
    with pytest.raises(Invalid, match="same"):
        validate([idealista, fotocasa], blocked=set())
