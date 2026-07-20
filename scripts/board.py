#!/usr/bin/env python3
"""The board: what the dashboard actually renders.

One rule governs everything:

    A listing holds EXACTLY ONE position — the most recent week it won.

From that single invariant you get all the behaviour the family asked for:
  * This week's winners sort to the top, in rank order.
  * A van that wins again is *promoted* into the new week rather than duplicated.
  * A van that gets replaced keeps the week it last won, so it simply drops below
    the new block — still there, still scrollable, just no longer top of the page.
  * Sections are (week desc, rank asc). No special-casing anywhere.

Never-won candidates never reach the board; they live in scripts/candidates.json.
"""

from datetime import date, datetime, timedelta

from harvest import same_vehicle


def iso_week(day: str | date) -> str:
    """'2026-07-13' -> '2026-W29'. Uses the ISO week, so weeks start on Monday."""
    if isinstance(day, str):
        day = datetime.strptime(day, "%Y-%m-%d").date()
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_start(week: str) -> str:
    """'2026-W29' -> '2026-07-13' (the Monday). Used for the section headings."""
    year, wk = week.split("-W")
    monday = date.fromisocalendar(int(year), int(wk), 1)
    return monday.isoformat()


# Fields Stage B (the research pass) is allowed to write onto a board entry.
# Anything else the model invents is ignored — the board schema stays ours.
RESEARCH_FIELDS = (
    "title", "price", "year", "km", "location", "photo", "url", "source",
    "score", "verdict", "flags", "specs",
)


def _sort_key(listing: dict) -> tuple:
    # Pinned reference first, then newest week, then best rank within that week.
    return (
        0 if listing.get("pinned") else 1,
        # Weeks are zero-padded ISO strings, so reverse-lexicographic == newest-first.
        _invert(listing.get("week", "")),
        listing.get("rank") or 99,
    )


def _invert(week: str) -> str:
    """Sort weeks descending inside an ascending sort, without a custom comparator."""
    # '2026-W29' -> each char flipped against 'z' so bigger weeks sort earlier.
    return "".join(chr(0x7E - ord(c)) for c in week)


def update_board(board: list, winners: list, week: str,
                 blocked_ids: set[str] | None = None) -> list:
    """Fold this week's winners into the board and return it, correctly ordered.

    `board`   — last week's board (list of listing dicts).
    `winners` — this week's ranked picks, each with at least `id` and `rank`.
    `week`    — ISO week string, e.g. '2026-W29'.
    `blocked_ids` — listings the family discarded; they are dropped entirely.
    """
    blocked = blocked_ids or set()
    monday = week_start(week)

    by_id: dict[str, dict] = {}
    for entry in board:
        if entry.get("id") in blocked:
            continue
        by_id[entry["id"]] = dict(entry)

    for w in winners:
        wid = w.get("id")
        if not wid or wid in blocked:
            continue

        # Promote in place if we've seen this exact id before, so history
        # (comments, stars, the id the Supabase tables key on) is preserved
        # rather than recreated. If it's a new id, check whether it's the same
        # physical vehicle as an existing card under a DIFFERENT id (relisted on
        # another source) — if so, promote that card instead of adding a second
        # one for the same van.
        target_id = wid
        if wid not in by_id:
            for existing_id, existing in by_id.items():
                if same_vehicle(w, existing):
                    target_id = existing_id
                    break

        entry = by_id.get(target_id, {})
        entry.update({k: v for k, v in w.items() if k in RESEARCH_FIELDS})
        entry["id"] = target_id
        entry["week"] = week
        entry["week_start"] = monday
        entry["rank"] = w.get("rank")
        entry.setdefault("status", "new")
        entry.setdefault("added_at", str(date.today()))
        by_id[target_id] = entry

    return sorted(by_id.values(), key=_sort_key)


def current_week(today: date | None = None) -> str:
    return iso_week(today or date.today())
