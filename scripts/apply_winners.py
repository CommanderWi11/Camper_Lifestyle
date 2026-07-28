#!/usr/bin/env python3
"""Stage C: validate this week's winners and fold them into the board.

This is the gate between a non-deterministic model and the family's live dashboard.
`claude -p` is good, but it is not a database — so nothing it produces reaches
docs/listings.json until it has passed every check below. If validation fails we
exit non-zero and weekly-search.sh refuses to commit, leaving last week's board
untouched. A stale board beats a corrupted one.
"""

import json
import sys
from pathlib import Path

import board
from harvest import (
    BLOCKLIST_FILE, LISTINGS_FILE, fetch_og_image, load_blocklist,
    load_candidates, load_listings, load_starred, make_id, same_vehicle,
)

WINNERS_FILE = Path(__file__).parent / "winners.json"
HISTORY_FILE = Path(__file__).parent.parent / "docs" / "history.json"
MAX_WINNERS = 5


class Invalid(Exception):
    """The model's output cannot be trusted. Abort rather than publish it."""


def blocked_listings(blocked: set[str]) -> list:
    """Full dicts (title/year/source) for every discarded id we have a record of,
    drawn from everywhere the family could have discarded it: the board, the
    harvester's own candidate pool, and manually-ingested history snapshots.

    Used with same_vehicle() below for CROSS-SOURCE matching — a discard on one
    portal (e.g. netcampers_fr) must also catch Stage B relisting the identical
    vehicle under a different portal (e.g. leboncoin), which has a different id
    (id = md5 of URL) and would never match on id alone. 2026-07-28: this exact
    scenario happened for real — same van (Challenger 287 GA Special Edition,
    same price/year/km/location), same discard, different portal, two runs in a
    row, before this existed.
    """
    known = load_candidates() + load_listings()
    if HISTORY_FILE.exists():
        for snapshot in json.loads(HISTORY_FILE.read_text()):
            known.extend(snapshot.get("entries", []))
    return [l for l in known if l.get("id") in blocked]


def validate(raw: object, blocked: set[str]) -> list:
    if not isinstance(raw, list):
        raise Invalid(f"expected a JSON list of winners, got {type(raw).__name__}")
    if len(raw) > MAX_WINNERS:
        raise Invalid(f"{len(raw)} winners — the board takes at most {MAX_WINNERS}")

    blocked_vehicles = blocked_listings(blocked)

    seen_ids: set[str] = set()
    winners = []  # survivors, original Stage B rank still attached — renumbered below
    dropped = 0

    for i, w in enumerate(raw):
        if not isinstance(w, dict):
            raise Invalid(f"winner #{i} is not an object")

        url = (w.get("url") or "").strip()
        source = (w.get("source") or "").strip()
        if not url.startswith("http"):
            raise Invalid(f"winner #{i} has no usable url: {url!r}")
        if not source:
            raise Invalid(f"winner #{i} has no source")

        # Reuse the harvested id when present so the family's stars and comments —
        # which are keyed on it in Supabase — survive. Otherwise derive it the same
        # way the harvester does, so a listing Claude found itself is addressable.
        wid = (w.get("id") or "").strip() or make_id(source, url)
        if wid in seen_ids:
            raise Invalid(f"duplicate winner id {wid}")

        # A discarded vehicle reappearing is NOT a trust problem with Stage B's
        # output the way a malformed field is — research-prompt.md tells Stage B
        # to check this itself, but that's prompt-following, not a guarantee (see
        # 2026-07-28: the Challenger 287 GA / netcampers_fr-de4813bc collision hit
        # this twice in a row even with the check in place — the SECOND time under
        # a different id entirely, relisted on leboncoin instead of netcampers_fr,
        # which is why this also checks same_vehicle() against every known blocked
        # listing, not just exact id equality). Dropping it here and continuing
        # means one bad entry costs a rank slot, not the whole ~12min Stage B run
        # and the day's board update.
        relisted_match = next((bv for bv in blocked_vehicles if same_vehicle(w, bv)), None)
        if wid in blocked or relisted_match:
            reason = wid if wid in blocked else f"same vehicle as blocked {relisted_match['id']}"
            print(f"  dropping {wid or '(no id)'} — discarded by the family "
                  f"({reason}), Stage B should not have re-included it", file=sys.stderr)
            dropped += 1
            continue

        for prev in winners:
            if same_vehicle(w, prev):
                raise Invalid(
                    f"winner {wid} and winner {prev['id']} look like the same "
                    f"vehicle from two different sources — the research pass "
                    f"ranked one van as two separate winners"
                )
        seen_ids.add(wid)

        rank = w.get("rank")
        if not isinstance(rank, int) or not 1 <= rank <= MAX_WINNERS:
            raise Invalid(f"winner {wid} has rank {rank!r}, expected 1..{MAX_WINNERS}")

        score = w.get("score")
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            raise Invalid(f"winner {wid} has score {score!r}, expected 0..100")

        verdict = (w.get("verdict") or "").strip()
        if len(verdict) < 20:
            raise Invalid(f"winner {wid} has no real verdict ({verdict!r})")

        w = dict(w)
        w["id"] = wid
        w.setdefault("flags", [])
        w.setdefault("specs", {})

        # Left-hand drive is a hard requirement (research-prompt.md) — make it a
        # machine-checked invariant like rank/score, not just prompt-trust.
        if w["specs"].get("drive_side") == "right":
            raise Invalid(f"winner {wid} has right-hand drive — hard requirement is LHD")

        winners.append(w)

    # Original ranks must always be unique. If nothing was dropped above, they
    # must also be consecutive from 1 — that's a real Stage B numbering mistake.
    # A gap caused BY a drop (e.g. {1,2,4,5} after rank 3 gets dropped) is
    # expected and fine — sort by Stage B's original rank to preserve its
    # relative ordering, then renumber 1..n so the published board has no gaps.
    orig_ranks = [w["rank"] for w in winners]
    if len(set(orig_ranks)) != len(orig_ranks):
        raise Invalid(f"rank assigned twice: {sorted(orig_ranks)}")
    if not dropped and orig_ranks and sorted(orig_ranks) != list(range(1, len(winners) + 1)):
        raise Invalid(f"ranks are not consecutive from 1: {sorted(orig_ranks)}")
    winners.sort(key=lambda w: w["rank"])
    for idx, w in enumerate(winners, start=1):
        w["rank"] = idx

    return winners


def main() -> int:
    if not WINNERS_FILE.exists():
        print(f"ERROR: {WINNERS_FILE} was never written — the research step failed.",
              file=sys.stderr)
        return 1

    try:
        raw = json.loads(WINNERS_FILE.read_text())
    except json.JSONDecodeError as exc:
        print(f"ERROR: winners.json is not valid JSON ({exc}).", file=sys.stderr)
        return 1

    blocked = load_blocklist()

    try:
        winners = validate(raw, blocked)
    except Invalid as exc:
        print(f"ERROR: refusing to publish — {exc}", file=sys.stderr)
        return 1

    if not winners:
        print("No winners this week; leaving the board as it is.")
        return 0

    # Every winner reaches the board with a real photo. A card whose source dropped
    # the image (lazy-load placeholder, price-on-request page) gets its og:image
    # pulled from the detail page — at most MAX_WINNERS fetches, best-effort.
    for w in winners:
        if not (w.get("photo") or "").startswith("http"):
            og = fetch_og_image(w.get("url", ""))
            if og:
                w["photo"] = og
                print(f"  backfilled photo for {w['id']} <- og:image")

    starred = load_starred()
    updated = board.update_board(
        load_listings(), winners, starred_ids=set(starred), blocked_ids=blocked,
    )
    LISTINGS_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2))

    favorites = sum(1 for l in updated if not l.get("rank"))
    print(f"Board updated:")
    for w in sorted(winners, key=lambda x: x["rank"]):
        flags = f"  ⚠ {len(w['flags'])} flag(s)" if w["flags"] else ""
        print(f"  #{w['rank']}  {w['score']:>3}  {w['title'][:52]}{flags}")
    print(f"{len(updated)} listings on the board ({len(winners)} in today's Top 5, "
          f"{favorites} favorite(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
