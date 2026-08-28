#!/usr/bin/env python3
"""Stage B helper: print one Idealista listing's rendered text to stdout.

Stage B (research-prompt.md) must use this for idealista.com detail pages
instead of the WebFetch tool — WebFetch has no browser fingerprint or session
cookie, so Idealista's DataDome anti-bot 403/CAPTCHAs it every time (see
`harvest.fetch_detail_page` for the full explanation and the incident that
surfaced this). Fotocasa/pisos.com are unaffected and still use WebFetch as
normal.

Usage: python3 scripts/idealista_detail.py <idealista-url>
"""
import sys

from harvest import fetch_detail_page


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("http"):
        print("usage: idealista_detail.py <idealista-url>", file=sys.stderr)
        return 2
    try:
        print(fetch_detail_page(sys.argv[1]))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
