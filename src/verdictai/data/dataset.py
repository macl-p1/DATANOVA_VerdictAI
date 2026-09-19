"""Canonical annotation I/O and BIO conversion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from verdictai.preprocessing.tokenizer import tokenize_with_offsets
from verdictai.schemas import LegalDocument


def iter_documents(directory: str | Path) -> Iterable[tuple[Path, dict]]:
    for path in sorted(Path(directory).glob("*.json")):
        with path.open(encoding="utf-8") as handle:
            yield path, json.load(handle)


def load_documents(directory: str | Path) -> list[LegalDocument]:
    return [LegalDocument.model_validate(item) for _, item in iter_documents(directory)]


def document_to_token_rows(document: LegalDocument) -> list[dict]:
    """Convert page-local spans to one BIO row per source page."""
    rows = []
    for page in document.pages:
        token_info = tokenize_with_offsets(page.text)
        tags = ["O"] * len(token_info)
        for entity in document.entities:
            if entity.page != page.page:
                continue
            overlapping = [i for i, (_, start, end) in enumerate(token_info) if start < entity.end and end > entity.start]
            for position, token_index in enumerate(overlapping):
                tags[token_index] = ("B-" if position == 0 else "I-") + entity.type
        rows.append({
            "document_id": document.document_id,
            "page": page.page,
            "language": document.language,
            "tokens": [token for token, _, _ in token_info],
            "ner_tags": tags,
        })
    return rows


def write_token_dataset(documents: list[LegalDocument], output: str | Path) -> int:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for document in documents:
            for row in document_to_token_rows(document):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    return count
