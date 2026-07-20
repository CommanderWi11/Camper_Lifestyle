"""The gate between a language model and the family's live dashboard.

`claude -p` does the judging, and it is good at it — but it is still a model, and a
bad run must never reach docs/listings.json. Every one of these tests describes a way
a run could go wrong and asserts that we refuse to publish rather than corrupt the board.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import apply_winners
from apply_winners import Invalid, validate


def ok(**over):
    w = {
        "id": "mundo_autocaravanas-1a2b3c4d",
        "url": "https://mundoautocaravanas.com/producto/roller-team-zefiro/",
        "source": "mundo_autocaravanas",
        "title": "Roller Team Zefiro — literas traseras",
        "price": 59900,
        "rank": 1,
        "score": 87,
        "verdict": "Literas traseras fijas y 4 cinturones de 3 puntos confirmados.",
    }
    w.update(over)
    return w


def test_a_good_run_validates():
    got = validate([ok()], blocked=set())
    assert got[0]["id"] == "mundo_autocaravanas-1a2b3c4d"
    assert got[0]["flags"] == []
    assert got[0]["specs"] == {}


def test_more_than_five_winners_is_refused():
    with pytest.raises(Invalid, match="at most 5"):
        validate([ok(id=f"x{i}", rank=i) for i in range(1, 7)], blocked=set())


def test_fewer_than_five_is_fine():
    """The Canary market is tiny. Three good vans beats five with two duds."""
    got = validate([ok(id="a", rank=1), ok(id="b", rank=2), ok(id="c", rank=3)], blocked=set())
    assert len(got) == 3


def test_a_discarded_listing_cannot_come_back_as_a_winner():
    """The whole point of the 🗑 button. If this ever passes, the feature is a lie."""
    with pytest.raises(Invalid, match="discarded"):
        validate([ok(id="rejected")], blocked={"rejected"})


def test_duplicate_ids_are_refused():
    with pytest.raises(Invalid, match="duplicate"):
        validate([ok(id="same", rank=1), ok(id="same", rank=2)], blocked=set())


def test_duplicate_ranks_are_refused():
    with pytest.raises(Invalid, match="rank 1 assigned twice"):
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
    """Listings Claude discovers on RentCamper have no harvested id — derive one
    the same way the harvester would, so stars and comments can attach to it."""
    got = validate([ok(id="", source="rentcamper", url="https://rentcampercanarias.com/x")],
                   blocked=set())
    assert got[0]["id"] == apply_winners.make_id("rentcamper", "https://rentcampercanarias.com/x")


def test_garbage_instead_of_a_list_is_refused():
    with pytest.raises(Invalid, match="expected a JSON list"):
        validate({"winners": []}, blocked=set())


def test_the_same_vehicle_ranked_twice_from_different_sources_is_refused():
    """If the research pass picks up the same van from two different sites as
    two separate 'winners', that is a research bug, not two real vehicles —
    refuse to publish rather than show the family a duplicate card."""
    coches_net = ok(id="coches_net-abc", rank=1, source="coches_net",
                     title="Etrusco T 7400 SB — perfilada, viajan y duermen 5, garaje grande")
    milanuncios = ok(id="milanuncios-xyz", rank=2, source="milanuncios",
                      title="Etrusco 7400SB — integral, camas gemelas traseras fijas + basculante")
    with pytest.raises(Invalid, match="same"):
        validate([coches_net, milanuncios], blocked=set())
