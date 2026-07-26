"""The board's promotion/demotion rules.

The whole "Top 5 today, Favorites persist, no archive" behaviour rests on one
invariant: a listing is on the board if it won today's Top 5, OR if the family
starred it. Everything else disappears. These tests pin it down.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import board


def winner(listing_id, rank, score=80, title=None, source="test", year=None):
    w = {
        "id": listing_id,
        "title": title or f"Autocaravana {listing_id}",
        "rank": rank,
        "score": score,
        "verdict": "Buena relación calidad-precio.",
        "url": f"https://example.com/{listing_id}",
        "source": source,
        "price": 50000,
    }
    if year is not None:
        w["year"] = year
    return w


def test_first_run_seeds_the_board():
    result = board.update_board([], [winner("a", 1), winner("b", 2)])
    assert [l["id"] for l in result] == ["a", "b"]
    assert [l["rank"] for l in result] == [1, 2]


def test_non_starred_dropped_winners_disappear_entirely():
    day1 = board.update_board([], [winner("old1", 1), winner("old2", 2)])
    day2 = board.update_board(day1, [winner("new1", 1)])

    assert [l["id"] for l in day2] == ["new1"], "no archive: dropped, unstarred winners vanish"


def test_starred_dropped_winner_survives_as_a_favorite():
    day1 = board.update_board([], [winner("old1", 1), winner("old2", 2)])
    day2 = board.update_board(day1, [winner("new1", 1)], starred_ids={"old2"})

    ids = [l["id"] for l in day2]
    assert ids == ["new1", "old2"], "starred old2 survives; unstarred old1 does not"
    favorite = next(l for l in day2 if l["id"] == "old2")
    assert favorite["rank"] is None, "a Favorite that fell out of the Top 5 is unranked"


def test_a_repeat_winner_moves_up_and_is_not_duplicated():
    day1 = board.update_board([], [winner("keeper", 1), winner("dropped", 2)])
    day2 = board.update_board(day1, [winner("fresh", 1), winner("keeper", 2)],
                              starred_ids={"keeper"})

    ids = [l["id"] for l in day2]
    assert ids.count("keeper") == 1, "a repeat winner must not appear twice"
    keeper = next(l for l in day2 if l["id"] == "keeper")
    assert keeper["rank"] == 2, "keeper is promoted back into today's Top 5"


def test_is_new_today_flags_first_time_winners_only():
    day1 = board.update_board([], [winner("a", 1), winner("b", 2)])
    assert all(l["is_new_today"] for l in day1), "everything is new on the first run"

    day2 = board.update_board(day1, [winner("a", 1), winner("c", 2)])
    a = next(l for l in day2 if l["id"] == "a")
    c = next(l for l in day2 if l["id"] == "c")
    assert a["is_new_today"] is False, "a repeat winner is not new"
    assert c["is_new_today"] is True, "a first-time winner is new"


def test_discarded_listings_are_removed_even_if_starred():
    day1 = board.update_board([], [winner("a", 1), winner("b", 2)], starred_ids={"a"})
    day2 = board.update_board(day1, [], starred_ids={"a"}, blocked_ids={"a"})
    assert [l["id"] for l in day2] == [], "a discard wins over a star — permanent means permanent"


def test_fewer_than_five_winners_is_allowed():
    """The market is thin some days. Three good vans beats five with two duds in it."""
    b = board.update_board([], [winner("a", 1), winner("b", 2), winner("c", 3)])
    assert len(b) == 3


def test_winner_fields_including_new_schema_fields_are_carried_onto_the_board():
    w = winner("a", 1, score=93)
    w.update({
        "country": "Alemania", "dealer_or_private": "concesionario",
        "vat_status": "IVA incluido", "checked_at": "2026-07-26",
        "specs": {"drive_side": "left"},
    })
    b = board.update_board([], [w])
    assert b[0]["score"] == 93
    assert b[0]["verdict"] == "Buena relación calidad-precio."
    assert b[0]["country"] == "Alemania"
    assert b[0]["dealer_or_private"] == "concesionario"
    assert b[0]["vat_status"] == "IVA incluido"
    assert b[0]["checked_at"] == "2026-07-26"
    assert b[0]["specs"]["drive_side"] == "left"


def test_a_relist_on_a_different_source_is_promoted_not_duplicated():
    """The real bug found live on the board 2026-07-20: the same Etrusco 7400SB
    won one run from coches_net and a later run from milanuncios — two
    different ids for the same van, which must fold into ONE card, not two."""
    day1 = board.update_board(
        [], [winner("coches_net-abc", 3, source="coches_net",
                     title="Etrusco T 7400 SB — perfilada, viajan y duermen 5, garaje grande")])
    day2 = board.update_board(
        day1, [winner("milanuncios-xyz", 4, source="milanuncios",
                       title="Etrusco 7400SB — integral, camas gemelas traseras fijas + basculante")])

    assert len(day2) == 1, "the relist must promote the existing card, not add a second one"
    entry = day2[0]
    # The original id is kept (that's what Supabase stars/comments/discards key on).
    assert entry["id"] == "coches_net-abc"
    assert entry["rank"] == 4
    # Its content reflects the newest winning data (the current live listing).
    assert "basculante" in entry["title"]


def test_two_different_vans_sharing_a_chassis_are_not_merged():
    result = board.update_board(
        [], [winner("mundo-a", 1, source="mundo_autocaravanas",
                     title="Fiat Ducato 2.8 JTD – ADRIA CORAL 660 SP G – ¡Reservada!"),
             winner("dm-b", 2, source="autocaravanas_dm",
                     title="Fiat Ducato 2.8 JTD – ELNAGH JOXY 10- ¡Reservada!")])
    assert len(result) == 2, "different models must not be collapsed just for sharing a chassis"
