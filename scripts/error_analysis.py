#!/usr/bin/env python
"""Produce an evidence-minimal error CSV from aligned token prediction JSONL."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--gold", required=True)
parser.add_argument("--predictions", required=True)
parser.add_argument("--output", default="artifacts/reports/error_analysis.csv")
args = parser.parse_args()
gold = [json.loads(line) for line in Path(args.gold).read_text(encoding="utf-8").splitlines()]
pred = [json.loads(line) for line in Path(args.predictions).read_text(encoding="utf-8").splitlines()]
if len(gold) != len(pred): raise SystemExit("Gold/prediction row counts differ.")
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
with Path(args.output).open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=["document_id", "entity_type", "gold_text", "predicted_text", "gold_label", "predicted_label", "confidence", "page", "error_type"]); writer.writeheader()
    for truth, guess in zip(gold, pred):
        for token, expected, actual in zip(truth["tokens"], truth["ner_tags"], guess["ner_tags"]):
            if expected == actual: continue
            error = "FALSE_NEGATIVE" if expected != "O" and actual == "O" else "FALSE_POSITIVE" if expected == "O" else "WRONG_ENTITY_TYPE"
            writer.writerow({"document_id": truth.get("document_id"), "entity_type": expected[2:] if expected != "O" else actual[2:], "gold_text": token if expected != "O" else "", "predicted_text": token if actual != "O" else "", "gold_label": expected, "predicted_label": actual, "confidence": guess.get("confidence", ""), "page": truth.get("page"), "error_type": error})
