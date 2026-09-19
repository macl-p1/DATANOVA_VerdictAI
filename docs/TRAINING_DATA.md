# Building a training corpus

The model learns only from annotated evidence spans. It cannot become reliable
by ingesting a large collection of PDFs or unannotated case text.

## Folder workflow

1. Put candidate annotated JSON documents in `data/training_uploads/`.
2. Run `python scripts/import_annotations.py --dry-run`.
3. Run `python scripts/import_annotations.py` after validation passes.
4. Run `python scripts/validate_dataset.py`, then train.

The importer copies validated documents into `data/annotations/`, which is the
only training source configured by default. Both folders are ignored by Git.

## Required annotation format

Each file is one document. Entity offsets are zero-based, the end offset is
exclusive, and the entity text must exactly equal the corresponding slice of
the page text.

```json
{
  "document_id": "UNIQUE_CASE_001",
  "language": "en",
  "source_type": "human_annotated",
  "case_group_id": "UNIQUE_CASE_001",
  "pages": [{"page": 1, "text": "The accused was arrested on 15 January 2024."}],
  "entities": [{"type": "ARREST_DATE", "text": "15 January 2024", "page": 1, "start": 28, "end": 43}]
}
```

Use separate `case_group_id` values for unrelated matters. Related documents
must share a case group so that they are never split across train, validation,
and test sets.

## Quality requirements

- Obtain and retain permission to use the documents.
- Remove or protect personal data under your organisation's policy.
- Use trained legal annotators and independent quality review.
- Include diverse courts, languages, document types, OCR quality, and writing styles.
- Keep a held-out test set that is never used for training decisions.

The current synthetic examples are only pipeline fixtures. They are not a
legal corpus and must not be used to assess real-case performance.
