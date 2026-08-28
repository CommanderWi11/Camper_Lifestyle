"""Stage E tests: the cross-track dedup safety net.

The two nightly tracks are area-disjoint by construction, but Tafira's own
LPGC-city-wide fallback search can surface a house the island-wide "gc" track
independently also finds — dedupe_tracks.dedupe() is what catches that before
the family sees the same house twice, once per tab.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import dedupe_tracks


def test_a_cross_track_duplicate_is_dropped_from_the_gc_side():
    tafira_board = [{
        "id": "idealista-aaa", "source": "idealista",
        "title": "Chalet independiente en Las Palmas con jardín privado, garaje amplio",
    }]
    gc_board = [{
        "id": "fotocasa-bbb", "source": "fotocasa",
        "title": "Casa independiente en Las Palmas con jardín privado, garaje amplio",
    }]
    kept, dropped = dedupe_tracks.dedupe(tafira_board, gc_board)
    assert kept == []
    assert len(dropped) == 1
    assert dropped[0][0]["id"] == "fotocasa-bbb"
    assert dropped[0][1]["id"] == "idealista-aaa"


def test_a_genuinely_different_house_is_not_dropped():
    tafira_board = [{
        "id": "idealista-aaa", "source": "idealista",
        "title": "Chalet independiente en Tafira Alta con jardín privado",
    }]
    gc_board = [{
        "id": "idealista-ccc", "source": "idealista",
        "title": "Villa moderna en Telde con piscina privada",
    }]
    kept, dropped = dedupe_tracks.dedupe(tafira_board, gc_board)
    assert [k["id"] for k in kept] == ["idealista-ccc"]
    assert dropped == []


def test_tafira_board_is_never_modified():
    tafira_board = [{
        "id": "idealista-aaa", "source": "idealista",
        "title": "Chalet independiente en Las Palmas con jardín privado, garaje amplio",
    }]
    gc_board = [{
        "id": "fotocasa-bbb", "source": "fotocasa",
        "title": "Casa independiente en Las Palmas con jardín privado, garaje amplio",
    }]
    before = list(tafira_board)
    dedupe_tracks.dedupe(tafira_board, gc_board)
    assert tafira_board == before


def test_multiple_gc_entries_only_the_duplicate_is_dropped():
    tafira_board = [{
        "id": "idealista-aaa", "source": "idealista",
        "title": "Chalet independiente en Las Palmas con jardín privado, garaje amplio",
    }]
    gc_board = [
        {"id": "fotocasa-bbb", "source": "fotocasa",
         "title": "Casa independiente en Las Palmas con jardín privado, garaje amplio"},
        {"id": "idealista-ddd", "source": "idealista",
         "title": "Chalet en Gáldar con vistas al mar, 4 dormitorios"},
    ]
    kept, dropped = dedupe_tracks.dedupe(tafira_board, gc_board)
    assert [k["id"] for k in kept] == ["idealista-ddd"]
    assert len(dropped) == 1


def test_main_is_a_noop_when_either_board_is_empty(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    populated = tmp_path / "populated.json"
    populated.write_text('[{"id": "x", "source": "idealista", "title": "Chalet en Telde"}]')

    monkeypatch.setattr(dedupe_tracks, "TAFIRA_LISTINGS", empty)
    monkeypatch.setattr(dedupe_tracks, "GC_LISTINGS", populated)

    assert dedupe_tracks.main() == 0
    assert "nothing to compare" in capsys.readouterr().out
    # GC file must be untouched when there was nothing to compare against.
    assert populated.read_text() == '[{"id": "x", "source": "idealista", "title": "Chalet en Telde"}]'
