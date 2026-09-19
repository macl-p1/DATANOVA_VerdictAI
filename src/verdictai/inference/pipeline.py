"""Chunked inference returning only ExtractionResult."""
from __future__ import annotations

from verdictai.inference.confidence import review_reasons
from verdictai.models.postprocessing import merge_bio_predictions
from verdictai.schemas import ExtractionResult


def predict_text(model, tokenizer, text: str, document_id: str, confidence_threshold: float = 0.70, max_length: int = 512, stride: int = 128) -> ExtractionResult:
    """Run chunked token classification while preserving source offsets.

    ``overflow_to_sample_mapping`` and ``offset_mapping`` are tokenizer
    bookkeeping fields, not model inputs.  In particular, passing the former
    to a Hugging Face model raises an unexpected-keyword error.
    """
    import torch
    if not document_id:
        raise ValueError("document_id must not be empty")
    if not text.strip():
        raise ValueError("text must not be empty")
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")
    if max_length < 2:
        raise ValueError("max_length must be at least 2")
    if not 0 <= stride < max_length:
        raise ValueError("stride must be non-negative and smaller than max_length")
    if not getattr(tokenizer, "is_fast", False):
        raise ValueError("a fast tokenizer is required to preserve source offsets")

    encoded = tokenizer(text, return_offsets_mapping=True, return_overflowing_tokens=True, truncation=True, max_length=max_length, stride=stride, return_tensors="pt", padding=True)
    offsets = encoded.pop("offset_mapping")
    encoded.pop("overflow_to_sample_mapping", None)
    try:
        device = next(model.parameters()).device
    except (AttributeError, StopIteration):
        device = None
    if device is not None:
        encoded = {name: value.to(device) for name, value in encoded.items()}
    model.eval()
    with torch.no_grad():
        logits = model(**encoded).logits
    probabilities = torch.softmax(logits, dim=-1)
    scores, labels = probabilities.max(dim=-1)
    tokens = []
    for chunk_index in range(labels.shape[0]):
        for index, label_id in enumerate(labels[chunk_index].tolist()):
            start, end = offsets[chunk_index][index].tolist()
            if start == end or label_id == 0:
                continue
            label = model.config.id2label.get(label_id, model.config.id2label.get(str(label_id)))
            if label is None:
                raise ValueError(f"model has no label for id {label_id}")
            tokens.append({"label": label, "text": text[start:end], "start": start, "end": end, "confidence": float(scores[chunk_index][index])})

    # Overlapping chunks contain the same source token more than once.  Keep
    # the highest-confidence occurrence before BIO reconstruction.
    unique_tokens = {}
    for token in tokens:
        key = (token["start"], token["end"])
        if key not in unique_tokens or token["confidence"] > unique_tokens[key]["confidence"]:
            unique_tokens[key] = token
    entities = merge_bio_predictions(sorted(unique_tokens.values(), key=lambda item: item["start"]), document_id)
    reasons = review_reasons(entities, confidence_threshold)
    return ExtractionResult(document_id=document_id, entities=entities, needs_review=bool(reasons), review_reasons=reasons)
