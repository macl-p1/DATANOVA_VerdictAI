"""Transparent regex baseline; it only extracts explicit text spans."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineMatch:
    type: str
    text: str
    start: int
    end: int
    confidence: float = 0.50


DATE = re.compile(r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4}|[A-Za-z]+\s+\d{1,2},\s*\d{4})\b")
SECTION = re.compile(r"\b(?:section|sections|sec\.?|u/s|under\s+section)\s+\d+(?:\s*(?:/|and|,)\s*\d+)*(?:\s+of\s+[A-Za-z. ]+)?", re.I)
CASE_ID = re.compile(r"\b(?:FIR|C\.C\.|CR|Case)\s*(?:No\.?\s*)?[A-Za-z0-9/-]+\b", re.I)


def extract(text: str) -> list[BaselineMatch]:
    matches: list[BaselineMatch] = []
    for pattern, entity_type in ((DATE, "ARREST_DATE"), (SECTION, "LEGAL_SECTION"), (CASE_ID, "CASE_ID")):
        matches.extend(BaselineMatch(entity_type, found.group(), found.start(), found.end()) for found in pattern.finditer(text))
    return sorted(matches, key=lambda item: (item.start, item.end))
