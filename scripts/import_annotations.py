#!/usr/bin/env python
"""Safely import validated annotation JSON files into the training corpus."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verdictai.data.dataset import load_documents
from verdictai.data.validation import normalized_hash, validate_directory
from verdictai.labels import entity_types, load_labels


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and import canonical annotated JSON documents.")
    parser.add_argument("--input", default="data/training_uploads", help="Staging directory containing annotated JSON files.")
    parser.add_argument("--output", default="data/annotations", help="Canonical training annotation directory.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and check collisions without copying files.")
    args = parser.parse_args()

    source, destination = Path(args.input), Path(args.output)
    report = validate_directory(source, entity_types(load_labels()))
    if not report.valid:
        print(report.render())
        raise SystemExit("Import aborted: staging dataset validation failed.")

    source_paths = sorted(source.glob("*.json"))
    if not source_paths:
        raise SystemExit(f"Import aborted: no JSON annotation files found in {source}.")
    destination.mkdir(parents=True, exist_ok=True)
    collisions = _collisions(load_documents(source), load_documents(destination), source_paths, destination)
    if collisions:
        raise SystemExit("Import aborted:\n" + "\n".join(f"- {item}" for item in collisions))
    if args.dry_run:
        print(f"Validation passed. {len(source_paths)} files are ready to import into {destination}.")
        return
    for path in source_paths:
        shutil.copy2(path, destination / path.name)
    print(f"Imported {len(source_paths)} validated files into {destination}.")


def _collisions(source_documents, existing_documents, source_paths: list[Path], destination: Path) -> list[str]:
    errors: list[str] = []
    existing_ids = {document.document_id for document in existing_documents}
    existing_hashes = {normalized_hash(document) for document in existing_documents}
    for path, document in zip(source_paths, source_documents):
        if (destination / path.name).exists():
            errors.append(f"destination filename already exists: {path.name}")
        if document.document_id in existing_ids:
            errors.append(f"document_id already exists: {document.document_id}")
        if normalized_hash(document) in existing_hashes:
            errors.append(f"duplicate document content: {document.document_id}")
    return errors


if __name__ == "__main__":
    main()
