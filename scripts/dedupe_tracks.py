#!/usr/bin/env python3
"""Stage E: cross-track dedup safety net.

The two nightly tracks are area-disjoint by construction — Tafira vs. Gran
Canaria EXCLUDING Tafira (see tracks.py, research-prompt-gc.md) — but Tafira's
own Las-Palmas-de-Gran-Canaria-city-wide FALLBACK search (used only when
Tafira alone is too thin — see IDEALISTA_SEARCH_AREAS in harvest.py) can
surface a non-Tafira LPGC house that the island-wide "gc" track could
independently also find. That is a real duplicate-risk case, not a
hypothetical one.

Runs after both tracks' apply_winners.py have published. Compares the two
boards with the same cross-source same_house() fuzzy matcher already used
everywhere else in this pipeline (harvest.py, board.py, apply_winners.py) and,
on a match, drops the duplicate from the Gran Canaria board — Tafira is the
primary/first track, so it wins ties. Does not touch board.py or re-rank
anything; a dropped duplicate just leaves that track with fewer than 5 for the
day, same as "not enough good candidates" already does.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import tracks
from harvest import same_house

TAFIRA_LISTINGS = tracks.TRACKS["tafira"]["listings_file"]
GC_LISTINGS = tracks.TRACKS["gc"]["listings_file"]


def _load(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def dedupe(tafira_board: list, gc_board: list) -> tuple[list, list]:
    """Returns (gc_board_with_duplicates_removed, dropped_pairs).

    `tafira_board` is never modified — Tafira is the primary track, so on a
    cross-track match the Gran Canaria side is the one that loses its slot.
    """
    dropped = []
    kept = []
    for gc_entry in gc_board:
        match = next((t for t in tafira_board if same_house(gc_entry, t)), None)
        if match:
            dropped.append((gc_entry, match))
        else:
            kept.append(gc_entry)
    return kept, dropped


def main() -> int:
    tafira_board = _load(TAFIRA_LISTINGS)
    gc_board = _load(GC_LISTINGS)
    if not tafira_board or not gc_board:
        print("[dedupe_tracks] one or both boards empty — nothing to compare.")
        return 0

    kept, dropped = dedupe(tafira_board, gc_board)
    if not dropped:
        print("[dedupe_tracks] no cross-track duplicates found.")
        return 0

    for gc_entry, tafira_entry in dropped:
        print(f"[dedupe_tracks] dropping {gc_entry.get('id')!r} from the Gran Canaria "
              f"board — same house as Tafira's {tafira_entry.get('id')!r}")
    GC_LISTINGS.write_text(json.dumps(kept, ensure_ascii=False, indent=2))
    print(f"[dedupe_tracks] {len(dropped)} duplicate(s) removed from the Gran Canaria board.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
