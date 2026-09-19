"""A deliberately simple, offset-preserving sentence splitter."""
from __future__ import annotations

import re


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    result = []
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+|\n+", text):
        end = match.start()
        if text[start:end].strip():
            result.append((text[start:end], start, end))
        start = match.end()
    if text[start:].strip():
        result.append((text[start:], start, len(text)))
    return result
