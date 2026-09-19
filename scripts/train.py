#!/usr/bin/env python
"""Fine-tune an IndicBERT encoder only after annotation validation succeeds."""
from __future__ import annotations
import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from verdictai.config import load_config
from verdictai.data.dataset import document_to_token_rows, load_documents
from verdictai.data.splits import split_documents
from verdictai.data.validation import validate_directory
from verdictai.labels import entity_types, label_maps, load_labels
from verdictai.models.ner_model import align_labels, load_token_classifier
from verdictai.training.trainer import set_seed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/training.yaml")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    report = validate_directory(config["dataset"]["annotations_dir"], entity_types(load_labels()), config["dataset"]["max_document_characters"])
    if not report.valid:
        print(report.render()); raise SystemExit("Training aborted: dataset validation failed.")
    documents = load_documents(config["dataset"]["annotations_dir"])
    if not documents:
        raise SystemExit("Training aborted: no annotations found.")
    seed = args.seed if args.seed is not None else config["training"]["seed"]
    set_seed(seed)
    split_rows = {name: [row for document in docs for row in document_to_token_rows(document)] for name, docs in split_documents(documents, seed).items()}
    if not split_rows["train"]:
        raise SystemExit("Training aborted: the training split has no token rows.")
    if not split_rows["validation"]:
        raise SystemExit("Training aborted: the validation split has no token rows; add more independent case groups.")
    label2id, id2label = label_maps()
    tokenizer, model = load_token_classifier(config["model"]["name"], config["model"].get("revision"), id2label, label2id)
    from datasets import Dataset
    from transformers import DataCollatorForTokenClassification, Trainer, TrainingArguments
    from verdictai.evaluation.metrics import entity_metrics

    def tokenise(batch):
        encoded = tokenizer(batch["tokens"], truncation=True, is_split_into_words=True, max_length=config["data"]["max_length"])
        encoded["labels"] = [align_labels([label2id[tag] for tag in tags], encoded.word_ids(batch_index=index)) for index, tags in enumerate(batch["ner_tags"])]
        return encoded
    datasets = {name: Dataset.from_list(rows).map(tokenise, batched=True, remove_columns=Dataset.from_list(rows).column_names) for name, rows in split_rows.items() if rows}
    output = Path(config["output"]["directory"]); output.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(output_dir=str(output), learning_rate=config["training"]["learning_rate"], num_train_epochs=config["training"]["num_train_epochs"], per_device_train_batch_size=config["training"]["per_device_train_batch_size"], per_device_eval_batch_size=config["training"]["per_device_eval_batch_size"], weight_decay=config["training"]["weight_decay"], warmup_ratio=config["training"]["warmup_ratio"], gradient_accumulation_steps=config["training"]["gradient_accumulation_steps"], fp16=config["training"]["fp16"], bf16=config["training"]["bf16"], logging_steps=config["training"]["logging_steps"], eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True, metric_for_best_model="f1", greater_is_better=True, report_to=[])
    def metrics(prediction):
        import numpy as np
        logits, labels = prediction
        predicted = np.argmax(logits, axis=-1)
        gold_sequences, pred_sequences = [], []
        for row_pred, row_gold in zip(predicted, labels):
            gold_sequences.append([id2label[int(g)] for g in row_gold if g != -100])
            pred_sequences.append([id2label[int(p)] for p, g in zip(row_pred, row_gold) if g != -100])
        return entity_metrics(gold_sequences, pred_sequences)["micro"]
    trainer = Trainer(model=model, args=training_args, train_dataset=datasets["train"], eval_dataset=datasets["validation"], tokenizer=tokenizer, data_collator=DataCollatorForTokenClassification(tokenizer), compute_metrics=metrics)
    trainer.train(); trainer.save_model(str(output)); tokenizer.save_pretrained(str(output))
    (output / "label_map.json").write_text(json.dumps(label2id, indent=2), encoding="utf-8")
    metadata = {"model": config["model"]["name"], "revision": config["model"].get("revision"), "task": "legal-ner", "dataset_version": config["dataset"]["version"], "training_date": datetime.now(timezone.utc).isoformat(), "labels": load_labels(), "max_length": config["data"]["max_length"], "stride": config["data"]["stride"], "epochs": config["training"]["num_train_epochs"], "random_seed": seed, "platform": platform.platform(), "git_commit": _git_commit()}
    (output / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _git_commit() -> str | None:
    try: return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception: return None


if __name__ == "__main__": main()
