"""Group-aware document-level splits with leakage checks."""
from __future__ import annotations

from collections import defaultdict
import random

from verdictai.data.validation import normalized_hash
from verdictai.schemas import LegalDocument


def split_documents(documents: list[LegalDocument], seed: int = 42, ratios: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> dict[str, list[LegalDocument]]:
    if len(ratios) != 3 or any(ratio <= 0 for ratio in ratios) or round(sum(ratios), 8) != 1.0:
        raise ValueError("split ratios must contain three positive values that sum to 1")
    groups: dict[str, list[LegalDocument]] = defaultdict(list)
    for document in documents:
        groups[document.case_group_id or document.document_id].append(document)
    grouped = list(groups.values())
    random.Random(seed).shuffle(grouped)
    targets = [len(documents) * ratio for ratio in ratios]
    result = {"train": [], "validation": [], "test": []}
    names = list(result)
    for group in grouped:
        name = min(names, key=lambda candidate: len(result[candidate]) / max(targets[names.index(candidate)], 1))
        result[name].extend(group)
    assert_no_leakage(result)
    return result


def assert_no_leakage(splits: dict[str, list[LegalDocument]]) -> None:
    ids: dict[str, str] = {}
    hashes: dict[str, str] = {}
    cases: dict[str, str] = {}
    for split, documents in splits.items():
        for document in documents:
            for value, tracker, label in ((document.document_id, ids, "document ID"), (normalized_hash(document), hashes, "content hash"), (document.case_group_id, cases, "case group")):
                if value is None:
                    continue
                if value in tracker and tracker[value] != split:
                    raise ValueError(f"{label} leakage between {tracker[value]} and {split}: {value}")
                tracker[value] = split
