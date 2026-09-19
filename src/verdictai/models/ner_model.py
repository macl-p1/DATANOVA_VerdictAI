"""Hugging Face token-classification construction and label alignment."""
from __future__ import annotations


def load_token_classifier(model_name: str, revision: str | None, id2label: dict[int, str], label2id: dict[str, int]):
    from transformers import AutoModelForTokenClassification, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
    model = AutoModelForTokenClassification.from_pretrained(model_name, revision=revision, num_labels=len(label2id), id2label=id2label, label2id=label2id, ignore_mismatched_sizes=True)
    return tokenizer, model


def align_labels(word_labels: list[int], word_ids: list[int | None]) -> list[int]:
    aligned = []
    previous = None
    for word_id in word_ids:
        if word_id is None:
            aligned.append(-100)
        elif word_id != previous:
            aligned.append(word_labels[word_id])
        else:
            label = word_labels[word_id]
            aligned.append(label + 1 if label > 0 and label % 2 == 1 else label)
        previous = word_id
    return aligned
