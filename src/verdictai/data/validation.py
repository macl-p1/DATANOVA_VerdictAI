"""Fail-closed validation for the canonical annotation format."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import unicodedata

from pydantic import ValidationError

from verdictai.labels import entity_types
from verdictai.schemas import LegalDocument


@dataclass
class ValidationReport:
    documents: int = 0
    entities: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_documents: int = 0

    @property
    def valid(self) -> bool:
        return not self.errors

    def render(self) -> str:
        status = "PASSED" if self.valid else "FAILED"
        return "\n".join([
            "Dataset validation", "------------------",
            f"Documents: {self.documents}", f"Entities: {self.entities}",
            f"Duplicate documents: {self.duplicate_documents}",
            f"Errors: {len(self.errors)}", f"Warnings: {len(self.warnings)}", "",
            f"STATUS: {status}", *self.errors, *self.warnings,
        ])


def normalized_hash(document: LegalDocument) -> str:
    text = "\n".join(page.text for page in document.pages)
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_directory(directory: str | Path, allowed_types: set[str], max_characters: int = 250000) -> ValidationReport:
    report = ValidationReport()
    seen_ids: set[str] = set()
    seen_hashes: dict[str, str] = {}
    for path in sorted(Path(directory).glob("*.json")):
        try:
            with path.open(encoding="utf-8") as handle:
                raw = json.load(handle)
            document = LegalDocument.model_validate(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
            report.errors.append(f"{path.name}: invalid JSON/schema: {exc}")
            continue
        report.documents += 1
        report.entities += len(document.entities)
        if document.document_id in seen_ids:
            report.errors.append(f"{path.name}: duplicate document_id {document.document_id}")
        seen_ids.add(document.document_id)
        total_chars = sum(len(page.text) for page in document.pages)
        if total_chars == 0:
            report.errors.append(f"{document.document_id}: empty document")
        if total_chars > max_characters:
            report.errors.append(f"{document.document_id}: exceeds max_document_characters")
        for page in document.pages:
            if not unicodedata.is_normalized("NFC", page.text):
                report.warnings.append(f"{document.document_id}: page {page.page} is not NFC-normalized")
        pages = {page.page: page.text for page in document.pages}
        if len(pages) != len(document.pages):
            report.errors.append(f"{document.document_id}: duplicate page numbers")
        occupied: dict[int, list[tuple[int, int]]] = {}
        for entity in document.entities:
            if entity.type not in allowed_types:
                report.errors.append(f"{document.document_id}: unknown entity type {entity.type}")
                continue
            page_text = pages.get(entity.page)
            if page_text is None:
                report.errors.append(f"{document.document_id}: entity page {entity.page} does not exist")
                continue
            if entity.end > len(page_text) or page_text[entity.start:entity.end] != entity.text:
                report.errors.append(f"{document.document_id}: invalid span for {entity.type} ({entity.start}:{entity.end})")
            ranges = occupied.setdefault(entity.page, [])
            if any(entity.start < end and entity.end > start for start, end in ranges):
                report.errors.append(f"{document.document_id}: overlapping entities on page {entity.page}")
            ranges.append((entity.start, entity.end))
        digest = normalized_hash(document)
        if digest in seen_hashes:
            report.duplicate_documents += 1
            report.errors.append(f"{document.document_id}: duplicate content of {seen_hashes[digest]}")
        else:
            seen_hashes[digest] = document.document_id
    return report


def validate_bio(tags: list[str], labels: set[str]) -> list[str]:
    errors = []
    previous_type = None
    for index, tag in enumerate(tags):
        if tag not in labels:
            errors.append(f"unknown label at token {index}: {tag}")
        if tag.startswith("I-") and previous_type != tag[2:]:
            errors.append(f"invalid I- sequence at token {index}: {tag}")
        previous_type = tag[2:] if tag.startswith(("B-", "I-")) else None
    return errors
