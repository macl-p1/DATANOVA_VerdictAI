# Evaluation

Hold out complete documents and all documents from the same `case_group_id`. Validation detects duplicate normalized text and split leakage. Never select the model using the test set.

The primary metric is exact entity-span precision, recall, and F1, with micro and per-entity reporting. Accuracy alone is inappropriate due to the dominant `O` class. Evaluate critical fields separately: arrest date, legal section, custody status, pending cases, and first-time offender status.

Report clean and OCR-noisy tests separately, and report each language separately only when those language test examples exist. Record dataset version, seed, model revision, hardware, time, configuration, and Git commit. Use `scripts/error_analysis.py` to classify false positives, false negatives, and wrong-type errors; boundary, normalization, OCR, tokenization, and ambiguity assessments require reviewed analysis rather than automatic claims.
