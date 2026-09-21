"""Text normalization and sentence splitting."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+|[\r\n]+")


def normalize_text(text: str) -> str:
    """Return stable NFC text with all whitespace collapsed."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def split_sentences(text: str) -> list[str]:
    """Split Korean or Latin prose at common sentence punctuation/newlines."""
    normalized = unicodedata.normalize("NFC", text or "").strip()
    if not normalized:
        return []
    return [part.strip() for part in _SENTENCE_END.split(normalized) if part.strip()]
