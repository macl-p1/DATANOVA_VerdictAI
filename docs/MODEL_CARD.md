# Model card

**Task:** token-level NER/information extraction from OCR or legal-document text. **Base model:** `ai4bharat/IndicBERTv2-MLM-only`, pinned in config with an inspected revision. **Output:** `ExtractionResult`, not a legal outcome.

Intended use is extracting explicitly present legal facts with evidence spans for human review and a separate deterministic system. Prohibited uses include determining release eligibility, guilt, innocence, sentence, or any legal conclusion.

No training data or performance figure is shipped with this repository. Measure exact span F1, per-entity recall, clean/OCR-noisy robustness, language-specific metrics, false positives, latency, and memory for each experiment. Confidence is model probability, not factual or legal certainty. Known limitations include OCR errors, absent context, format variation, document length, negation interpretation, and no entity-relation linking.
