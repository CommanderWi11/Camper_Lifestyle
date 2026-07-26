#!/usr/bin/env python3
"""The board: what the dashboard actually renders.

One rule governs everything:

    A listing is on the board if it won today's Top 5, OR if the family starred it.
    Everything else disappears — there is no week-by-week archive.

From that single invariant you get all the behaviour the family asked for:
  * Today's Top 5 always reflects the latest research pass, refreshed daily.
  * A van that wins again is *promoted* into today's Top 5 rather than duplicated.
  * A van that gets replaced but is starred drops to the Favorites section
    (rank=None) instead of vanishing or cluttering an archive.
  * A van that gets replaced and was never starred simply disappears.

Never-won candidates never reach the board; they live in scripts/candidates.json.
"""

from datetime import date

from harvest import same_vehicle

# Fields Stage B (the research pass) is allowed to write onto a board entry.
# Anything else the model invents is ignored — the board schema stays ours.
RESEARCH_FIELDS = (
    "title", "price", "year", "km", "country", "location", "photo", "url", "source",
    "score", "verdict", "flags", "specs", "dealer_or_private", "vat_status",
    "checked_at",
)


def _sort_key(listing: dict) -> tuple:
    # Today's Top 5 first, in rank order; Favorites (rank None) after, stable by id
    # (the dashboard re-sorts Favorites by star recency client-side, using the
    # `camper_stars.created_at` timestamp it already has — the board's own order
    # only needs to be deterministic, not meaningful).
    rank = listing.get("rank")
    return (0, rank) if rank else (1, listing.get("id", ""))


def update_board(board: list, winners: list, starred_ids: set[str] | None = None,
                 blocked_ids: set[str] | None = None) -> list:
    """Fold today's winners into the board and return it, correctly ordered.

    `board`        — the board as of the last run (list of listing dicts).
    `winners`      — today's ranked picks, each with at least `id` and `rank`.
    `starred_ids`  — listing ids the family has starred; kept as Favorites
                     (rank set to None) even after they drop out of the Top 5.
    `blocked_ids`  — listings the family discarded; dropped entirely, permanently.
    """
    starred = starred_ids or set()
    blocked = blocked_ids or set()

    by_id: dict[str, dict] = {}
    previous_top5_ids: set[str] = set()
    for entry in board:
        if entry.get("id") in blocked:
            continue
        by_id[entry["id"]] = dict(entry)
        if entry.get("rank"):
            previous_top5_ids.add(entry["id"])

    winner_ids: set[str] = set()
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
        entry["rank"] = w.get("rank")
        entry["is_new_today"] = target_id not in previous_top5_ids
        entry.setdefault("status", "new")
        entry.setdefault("added_at", str(date.today()))
        by_id[target_id] = entry
        winner_ids.add(target_id)

    # Anything not in today's winners survives only if starred (as a Favorite,
    # rank=None) — everything else simply disappears. This one loop is the whole
    # "Top 5 refreshes daily, Favorites persist, no archive" behaviour.
    for lid in list(by_id):
        if lid in winner_ids:
            continue
        if lid in starred:
            by_id[lid]["rank"] = None
            by_id[lid]["is_new_today"] = False
        else:
            del by_id[lid]

    return sorted(by_id.values(), key=_sort_key)
