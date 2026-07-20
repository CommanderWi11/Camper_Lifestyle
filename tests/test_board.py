"""The board's promotion/demotion rules.

The whole "top 5 this week, older winners scroll below" behaviour rests on one
invariant: a listing holds EXACTLY ONE position on the board, namely the most
recent week it won. Everything else (sections, ordering, no-duplicates) falls out
of that. These tests pin it down.
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


def test_first_week_seeds_the_board():
    result = board.update_board([], [winner("a", 1), winner("b", 2)], "2026-W29")
    assert [l["id"] for l in result] == ["a", "b"]
    assert all(l["week"] == "2026-W29" for l in result)
    assert [l["rank"] for l in result] == [1, 2]


def test_new_winners_sort_above_previous_week():
    wk29 = board.update_board([], [winner("old1", 1), winner("old2", 2)], "2026-W29")
    wk30 = board.update_board(wk29, [winner("new1", 1)], "2026-W30")

    # This week's winner is on top; last week's fall below but are still present.
    assert [l["id"] for l in wk30] == ["new1", "old1", "old2"]
    assert wk30[0]["week"] == "2026-W30"
    assert wk30[1]["week"] == "2026-W29"


def test_a_repeat_winner_moves_up_and_is_not_duplicated():
    wk29 = board.update_board([], [winner("keeper", 1), winner("dropped", 2)], "2026-W29")
    wk30 = board.update_board(wk29, [winner("fresh", 1), winner("keeper", 2)], "2026-W30")

    ids = [l["id"] for l in wk30]
    assert ids.count("keeper") == 1, "a repeat winner must not appear twice"
    # keeper is promoted into this week (rank 2); dropped falls to the old section.
    assert ids == ["fresh", "keeper", "dropped"]
    keeper = next(l for l in wk30 if l["id"] == "keeper")
    assert keeper["week"] == "2026-W30" and keeper["rank"] == 2
    dropped = next(l for l in wk30 if l["id"] == "dropped")
    assert dropped["week"] == "2026-W29", "a demoted listing keeps the week it last won"


def test_demoted_listing_keeps_its_old_rank_for_stable_ordering():
    wk29 = board.update_board([], [winner("a", 1), winner("b", 2), winner("c", 3)], "2026-W29")
    wk30 = board.update_board(wk29, [winner("z", 1)], "2026-W30")
    old = [l for l in wk30 if l["week"] == "2026-W29"]
    assert [l["rank"] for l in old] == [1, 2, 3], "old section stays in its original order"


def test_board_is_sorted_by_week_desc_then_rank_asc():
    b = board.update_board([], [winner("a", 2), winner("b", 1)], "2026-W29")
    b = board.update_board(b, [winner("c", 2), winner("d", 1)], "2026-W30")
    assert [l["id"] for l in b] == ["d", "c", "b", "a"]


def test_pinned_reference_survives_and_is_never_ranked():
    ref = {"id": "manual-concorde-liner-ref", "title": "Referencia", "pinned": True,
           "status": "reference", "price": 0, "url": "", "source": "manual"}
    result = board.update_board([ref], [winner("a", 1)], "2026-W29")
    assert result[0]["id"] == "manual-concorde-liner-ref", "pinned reference stays on top"
    assert "rank" not in result[0] or result[0].get("rank") is None
    assert [l["id"] for l in result[1:]] == ["a"]


def test_discarded_listings_are_removed_from_the_board():
    b = board.update_board([], [winner("a", 1), winner("b", 2)], "2026-W29")
    b = board.update_board(b, [], "2026-W30", blocked_ids={"a"})
    assert [l["id"] for l in b] == ["b"], "a discarded listing disappears from the board"


def test_fewer_than_five_winners_is_allowed():
    """The Canary market is thin. Three good vans beats five with two duds in it."""
    b = board.update_board([], [winner("a", 1), winner("b", 2), winner("c", 3)], "2026-W29")
    assert len(b) == 3


def test_winner_fields_are_carried_onto_the_board():
    b = board.update_board([], [winner("a", 1, score=93)], "2026-W29")
    assert b[0]["score"] == 93
    assert b[0]["verdict"] == "Buena relación calidad-precio."
    assert b[0]["week_start"] == "2026-07-13", "W29 of 2026 starts Monday 13 July"


def test_a_relist_on_a_different_source_is_promoted_not_duplicated():
    """The real bug found live on the board 2026-07-20: the same Etrusco 7400SB
    won one week from coches_net and a later week from milanuncios — two
    different ids for the same van, which must fold into ONE card, not two."""
    wk29 = board.update_board(
        [], [winner("coches_net-abc", 3, source="coches_net",
                     title="Etrusco T 7400 SB — perfilada, viajan y duermen 5, garaje grande")],
        "2026-W29")
    wk30 = board.update_board(
        wk29, [winner("milanuncios-xyz", 4, source="milanuncios",
                       title="Etrusco 7400SB — integral, camas gemelas traseras fijas + basculante")],
        "2026-W30")

    assert len(wk30) == 1, "the relist must promote the existing card, not add a second one"
    entry = wk30[0]
    # The original id is kept (that's what Supabase stars/comments/discards key on).
    assert entry["id"] == "coches_net-abc"
    assert entry["week"] == "2026-W30" and entry["rank"] == 4
    # Its content reflects the newest winning data (the current live listing).
    assert "basculante" in entry["title"]


def test_two_different_vans_sharing_a_chassis_are_not_merged():
    wk29 = board.update_board(
        [], [winner("mundo-a", 1, source="mundo_autocaravanas",
                     title="Fiat Ducato 2.8 JTD – ADRIA CORAL 660 SP G – ¡Reservada!")],
        "2026-W29")
    wk30 = board.update_board(
        wk29, [winner("dm-b", 1, source="autocaravanas_dm",
                       title="Fiat Ducato 2.8 JTD – ELNAGH JOXY 10- ¡Reservada!")],
        "2026-W30")
    assert len(wk30) == 2, "different models must not be collapsed just for sharing a chassis"


def test_iso_week_and_week_start_agree():
    assert board.iso_week("2026-07-13") == "2026-W29"
    assert board.week_start("2026-W29") == "2026-07-13"
    # Sunday still belongs to the week that began the previous Monday.
    assert board.iso_week("2026-07-19") == "2026-W29"
    assert board.iso_week("2026-07-20") == "2026-W30"
