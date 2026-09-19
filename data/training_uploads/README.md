# Training dataset drop folder

Put annotated JSON files here before importing them into the training corpus.
Each file must follow the canonical format used in `data/annotations/`; see
`docs/TRAINING_DATA.md` for the required fields and offset rules.

This folder is Git-ignored so that public or sensitive source materials are not
accidentally committed. Do not put PDFs, screenshots, or unannotated OCR text
here and expect training to work: they must be converted to text and annotated
with evidence spans first.

Validate and import the files with:

```powershell
python scripts/import_annotations.py
```

Use `--dry-run` to check the data without copying it. The importer refuses
duplicate filenames, document IDs, and document content.
