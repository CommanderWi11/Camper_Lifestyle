"""Per-track configuration for the two nightly search tracks.

Both tracks share the exact same pipeline shape (harvest.py -> claude -p
research -> apply_winners.py -> board.py) and the same blocklist/starred
stores (a discard or a favorite sticks regardless of which track found the
house) — only the search area, the bedroom hard-gate, and the research prompt
differ. This is the single source of truth for those per-track differences,
replacing what used to be three independent, unlinked copies of the
price/bedroom gate (params.json, apply_winners.py's literals, and
research-prompt.md's prose).
"""

from pathlib import Path

_SCRIPTS = Path(__file__).parent
_DOCS = _SCRIPTS.parent / "docs"

TRACKS = {
    "tafira": {
        "label": "Tafira",
        "params_file": _SCRIPTS / "params.json",
        "candidates_file": _SCRIPTS / "candidates.json",
        "winners_file": _SCRIPTS / "winners.json",
        "listings_file": _DOCS / "listings.json",
        "archive_file": _DOCS / "archive.json",
        "research_prompt": _SCRIPTS / "research-prompt.md",
        "min_bedrooms_gate": 3,
    },
    "gc": {
        "label": "Gran Canaria",
        "params_file": _SCRIPTS / "params-gc.json",
        "candidates_file": _SCRIPTS / "candidates-gc.json",
        "winners_file": _SCRIPTS / "winners-gc.json",
        "listings_file": _DOCS / "listings-gc.json",
        "archive_file": _DOCS / "archive-gc.json",
        "research_prompt": _SCRIPTS / "research-prompt-gc.md",
        "min_bedrooms_gate": 4,
    },
}

DEFAULT_TRACK = "tafira"
