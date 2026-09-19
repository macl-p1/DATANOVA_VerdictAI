# VerdictAI ML

VerdictAI extracts explicit, evidence-backed facts from Indian legal documents. It is not a release-eligibility, guilt, sentencing, or legal-advice model.

```text
OCR text -> IndicBERT NER -> validated ExtractionResult -> deterministic rules -> RuleResult
```

The extraction model has no code path to a legal decision. Every entity includes original text, offsets, page (when supplied), normalized value where deterministic, and model confidence. Missing facts remain missing; uncertain facts produce `needs_review`.

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/validate_dataset.py
python scripts/prepare_dataset.py
python scripts/split_dataset.py
python scripts/train.py --config configs/training.yaml
```

`configs/base.yaml` records `ai4bharat/IndicBERTv2-MLM-only` revision `e726058`, inspected on 2026-09-19. It is a 26-language BERT encoder checkpoint and is loaded with `AutoModelForTokenClassification`; verify availability and revision again before a production training run.

## Canonical input

Place one JSON document per file in `data/annotations/`:

```json
{
  "document_id": "CASE_000001",
  "language": "en",
  "source_type": "synthetic",
  "pages": [{"page": 1, "text": "The accused was arrested on 15 January 2024."}],
  "entities": [{"type": "ARREST_DATE", "text": "15 January 2024", "page": 1, "start": 29, "end": 44}]
}
```

Validate before training. The validator rejects invalid spans, unknown entity types, duplicate IDs/content, empty or oversized documents, overlap, invalid pages, malformed JSON, and non-matching entity text. Splits are document/case-group based and detect cross-split IDs, content hashes, and case groups.

## Inference

```bash
python scripts/predict.py --model artifacts/models/verdictai-indicbert --input sample.txt
python scripts/serve.py --model artifacts/models/verdictai-indicbert
```

The optional service exposes `POST /predict` with `document_id` and `text`. It returns extraction evidence only. PDF OCR is intentionally an explicit integration boundary; provide OCR text rather than silently using unreliable PDF extraction.

## Evaluation

Use an untouched held-out test split. `scripts/evaluate.py` reports exact entity span precision, recall, and F1; it does not manufacture scores. `scripts/error_analysis.py` emits error records without logging whole source documents.

The regex baseline extracts explicit date, section, and case-ID patterns, providing a transparent comparison point. OCR-noise and multilingual experiments must be separately annotated and reported; no multilingual claim is made without measured data.

## Privacy and limits

Raw/processed documents and artifacts are Git-ignored. Use controlled storage and document IDs in reports. Confidence is a prediction score, never legal certainty. NER does not solve relation extraction: with multiple accused, the baseline does not establish which person owns which fact. Human review remains required for low-confidence, contradictory, or required-missing facts.
