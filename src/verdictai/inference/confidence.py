"""Confidence is a model-score policy, never legal certainty."""
from __future__ import annotations


def review_reasons(entities, threshold: float) -> list[str]:
    reasons = [f"low confidence {entity.type}: {entity.evidence.confidence:.2f}" for entity in entities if entity.evidence.confidence < threshold]
    return reasons
