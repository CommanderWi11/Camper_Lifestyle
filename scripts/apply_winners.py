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
    load_listings, make_id, same_vehicle,
)

WINNERS_FILE = Path(__file__).parent / "winners.json"
MAX_WINNERS = 5


class Invalid(Exception):
    """The model's output cannot be trusted. Abort rather than publish it."""


def validate(raw: object, blocked: set[str]) -> list:
    if not isinstance(raw, list):
        raise Invalid(f"expected a JSON list of winners, got {type(raw).__name__}")
    if len(raw) > MAX_WINNERS:
        raise Invalid(f"{len(raw)} winners — the board takes at most {MAX_WINNERS}")

    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    winners = []

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
        if wid in blocked:
            raise Invalid(f"{wid} was discarded by the family but came back as a winner")
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
        if rank in seen_ranks:
            raise Invalid(f"rank {rank} assigned twice")
        seen_ranks.add(rank)

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
        winners.append(w)

    # Ranks must be 1..n with no gaps, otherwise the ordering is a lie.
    if seen_ranks and sorted(seen_ranks) != list(range(1, len(winners) + 1)):
        raise Invalid(f"ranks are not consecutive from 1: {sorted(seen_ranks)}")

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

    week = board.current_week()
    updated = board.update_board(load_listings(), winners, week, blocked_ids=blocked)
    LISTINGS_FILE.write_text(json.dumps(updated, ensure_ascii=False, indent=2))

    print(f"Board updated for {week} ({board.week_start(week)}):")
    for w in sorted(winners, key=lambda x: x["rank"]):
        flags = f"  ⚠ {len(w['flags'])} flag(s)" if w["flags"] else ""
        print(f"  #{w['rank']}  {w['score']:>3}  {w['title'][:52]}{flags}")
    print(f"{len(updated)} listings on the board.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
