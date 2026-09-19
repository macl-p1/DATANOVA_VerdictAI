"""Deterministic transformation from token predictions to evidence-bearing entities."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Iterable

from verdictai.schemas import Evidence, ExtractedEntity


def normalize_date(value: str) -> str | None:
    cleaned = value.strip()
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y", "%d %B %Y", "%d %B, %Y", "%B %d, %Y"):
        candidate = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", cleaned, flags=re.I)
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def normalize_section(value: str) -> str | None:
    match = re.search(r"(?:section|sections|sec\.?|u/s|under\s+section)\s+(.+)", value, re.I)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1).strip()).upper()


def merge_bio_predictions(predictions: Iterable[dict], document_id: str, page: int | None = None) -> list[ExtractedEntity]:
    """Merge adjacent BIO words. Each prediction needs text, label, start, end, confidence."""
    entities: list[ExtractedEntity] = []
    current: dict | None = None
    for token in predictions:
        label = token["label"]
        prefix, _, kind = label.partition("-")
        continuation = current and prefix == "I" and kind == current["type"] and token["start"] <= current["end"] + 1
        if prefix not in {"B", "I"}:
            if current:
                entities.append(_entity_from_current(current, document_id, page))
                current = None
            continue
        if not continuation:
            if current:
                entities.append(_entity_from_current(current, document_id, page))
            current = {"type": kind, "text": token["text"], "start": token["start"], "end": token["end"], "scores": [token["confidence"]]}
        else:
            current["text"] += " " + token["text"]
            current["end"] = token["end"]
            current["scores"].append(token["confidence"])
    if current:
        entities.append(_entity_from_current(current, document_id, page))
    return _deduplicate(entities)


def _entity_from_current(current: dict, document_id: str, page: int | None) -> ExtractedEntity:
    value = current["text"]
    normalized = normalize_date(value) if current["type"] in {"ARREST_DATE", "RELEASE_DATE"} else normalize_section(value) if current["type"] == "LEGAL_SECTION" else None
    return ExtractedEntity(type=current["type"], value=value, normalized_value=normalized, evidence=Evidence(
        document_id=document_id, text=value, page=page, start=current["start"], end=current["end"], confidence=sum(current["scores"]) / len(current["scores"]),
    ))


def _deduplicate(entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
    seen = set()
    result = []
    for entity in entities:
        key = (entity.type, entity.evidence.page, entity.evidence.start, entity.evidence.end, entity.value)
        if key not in seen:
            result.append(entity)
            seen.add(key)
    return result
