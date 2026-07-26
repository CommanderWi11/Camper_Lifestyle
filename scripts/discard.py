#!/usr/bin/env python3
"""Discard a listing from the terminal.

The 🗑 button in the dashboard is the normal way to do this — it writes to Supabase
and syncs across devices. This CLI is the backend-free path: it appends to
scripts/blocklist.json, which harvest.py reads before it scrapes anything. Useful
when Supabase is down, and it keeps the discard list reviewable in a git diff.

    ./scripts/discard.py wallapop-1b1ee087            # discard
    ./scripts/discard.py --undo wallapop-1b1ee087     # bring it back
    ./scripts/discard.py --list
"""
import argparse
import json
import sys

from harvest import BLOCKLIST_FILE, _load_json


def save(ids: list[str]) -> None:
    BLOCKLIST_FILE.write_text(json.dumps(sorted(set(ids)), ensure_ascii=False, indent=2))


def main() -> int:
    p = argparse.ArgumentParser(description="Discard listings so the weekly search never resurfaces them.")
    p.add_argument("listing_id", nargs="*", help="listing id(s), e.g. campermax-1a2b3c4d")
    p.add_argument("--undo", action="store_true", help="remove the id(s) from the blocklist")
    p.add_argument("--list", action="store_true", dest="show", help="print the current blocklist")
    args = p.parse_args()

    blocked = list(_load_json(BLOCKLIST_FILE))

    if args.show:
        print("\n".join(blocked) if blocked else "(nothing discarded)")
        return 0

    if not args.listing_id:
        p.print_help()
        return 1

    if args.undo:
        kept = [b for b in blocked if b not in args.listing_id]
        save(kept)
        print(f"Restored {len(blocked) - len(kept)}. {len(kept)} still discarded.")
    else:
        save(blocked + args.listing_id)
        added = len(set(args.listing_id) - set(blocked))
        print(f"Discarded {added}. {len(set(blocked) | set(args.listing_id))} total.")
        print("They will not appear in the next daily search.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
