"""Text folding and tokenization shared by indexing and querying.

Danish/German letters are transliterated (ø->oe, å->aa, ß->ss ...) so that
"Stühle" == "Stuehle" and "grå" == "graa" on both sides of the index.
"""
from __future__ import annotations

import html
import re
import unicodedata

_TRANSLIT = str.maketrans({
    "æ": "ae", "ø": "oe", "å": "aa", "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Æ": "ae", "Ø": "oe", "Å": "aa", "Ä": "ae", "Ö": "oe", "Ü": "ue",
})
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", html.unescape(text)).strip()


def fold(text: str | None) -> str:
    """Lowercase, transliterate Nordic/German letters, drop remaining accents."""
    if not text:
        return ""
    text = text.lower().translate(_TRANSLIT)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def tokenize(text: str | None) -> list[str]:
    return _TOKEN_RE.findall(fold(text))
