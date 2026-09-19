"""Configurable BIO label definitions."""
from __future__ import annotations

from pathlib import Path
import yaml


def load_labels(path: str | Path = "configs/labels.yaml") -> list[str]:
    with Path(path).open(encoding="utf-8") as handle:
        labels = (yaml.safe_load(handle) or {}).get("labels", [])
    if not labels or labels[0] != "O":
        raise ValueError("labels.yaml must start with the O label")
    if len(labels) != len(set(labels)):
        raise ValueError("labels.yaml contains duplicate labels")
    return labels


def label_maps(path: str | Path = "configs/labels.yaml") -> tuple[dict[str, int], dict[int, str]]:
    labels = load_labels(path)
    forward = {label: index for index, label in enumerate(labels)}
    return forward, {index: label for label, index in forward.items()}


def entity_types(labels: list[str]) -> set[str]:
    return {label.split("-", 1)[1] for label in labels if label != "O"}
