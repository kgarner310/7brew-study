"""Deterministic plain-text normalization.

Normalization exists so that change detection reports *legal* changes. A
rotating session token in a footer or a reflowed paragraph must not read as an
amendment; an altered word must.

Kept intentionally conservative: it never reorders, summarizes, or rewrites
content. Any change to this function's output for unchanged input requires
bumping ``NORMALIZER_VERSION``.
"""

from __future__ import annotations

import re
import unicodedata

# Named explicitly rather than embedded as literals: invisible characters in
# source are unreviewable, and these two sets are load-bearing for hash stability.
ZERO_WIDTH_CHARS = (
    "\u200b"  # ZERO WIDTH SPACE
    "\u200c"  # ZERO WIDTH NON-JOINER
    "\u200d"  # ZERO WIDTH JOINER
    "\u2060"  # WORD JOINER
    "\ufeff"  # ZERO WIDTH NO-BREAK SPACE / BOM
)
HORIZONTAL_SPACE_CHARS = (
    " "
    "\t"
    "\u00a0"  # NO-BREAK SPACE
    "\u2007"  # FIGURE SPACE
    "\u202f"  # NARROW NO-BREAK SPACE
)

_ZERO_WIDTH = dict.fromkeys(map(ord, ZERO_WIDTH_CHARS), None)
_WHITESPACE_RUN = re.compile(f"[{re.escape(HORIZONTAL_SPACE_CHARS)}]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+$", re.MULTILINE)


def normalize_text(raw: str) -> str:
    """Return canonical plain text for hashing and storage.

    Steps: NFC composition, zero-width removal, CRLF folding, horizontal
    whitespace collapse, trailing-space strip, blank-run collapse.
    """
    text = unicodedata.normalize("NFC", raw)
    text = text.translate(_ZERO_WIDTH)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN.sub(" ", text)
    text = _TRAILING_WS.sub("", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()
