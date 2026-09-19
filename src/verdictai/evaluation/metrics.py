"""Exact span metrics for BIO sequences."""
from __future__ import annotations

from collections import Counter


def spans(tags: list[str]) -> set[tuple[str, int, int]]:
    output, current_type, start = set(), None, None
    for index, tag in enumerate([*tags, "O"]):
        prefix, _, kind = tag.partition("-")
        if current_type and (prefix != "I" or kind != current_type):
            output.add((current_type, start, index))
            current_type, start = None, None
        if prefix == "B" or (prefix == "I" and current_type is None):
            current_type, start = kind, index
    return output


def entity_metrics(gold_sequences: list[list[str]], predicted_sequences: list[list[str]]) -> dict:
    if len(gold_sequences) != len(predicted_sequences):
        raise ValueError("gold and predicted sequence counts must match")
    counts = Counter()
    per_type: dict[str, Counter] = {}
    for index, (gold, predicted) in enumerate(zip(gold_sequences, predicted_sequences)):
        if len(gold) != len(predicted):
            raise ValueError(f"gold and predicted token counts differ at sequence {index}")
        gold_spans, pred_spans = spans(gold), spans(predicted)
        for entity_type in {item[0] for item in gold_spans | pred_spans}:
            bucket = per_type.setdefault(entity_type, Counter())
            bucket["tp"] += len({span for span in gold_spans & pred_spans if span[0] == entity_type})
            bucket["fp"] += len({span for span in pred_spans - gold_spans if span[0] == entity_type})
            bucket["fn"] += len({span for span in gold_spans - pred_spans if span[0] == entity_type})
        counts["tp"] += len(gold_spans & pred_spans)
        counts["fp"] += len(pred_spans - gold_spans)
        counts["fn"] += len(gold_spans - pred_spans)
    return {"micro": _scores(counts), "per_entity": {name: _scores(value) for name, value in sorted(per_type.items())}}


def _scores(counts: Counter) -> dict[str, float]:
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0.0
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0.0
    return {"precision": precision, "recall": recall, "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
