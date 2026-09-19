#!/usr/bin/env python
"""Evaluate a saved model against an explicit held-out split."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.evaluation.metrics import entity_metrics
from verdictai.evaluation.reports import render_metrics

parser = argparse.ArgumentParser(description="Summarise precomputed BIO predictions without fabricated scores.")
parser.add_argument("--gold", required=True, help="JSONL with ner_tags")
parser.add_argument("--predictions", required=True, help="JSONL with ner_tags")
parser.add_argument("--output", default="artifacts/reports/evaluation.txt")
args = parser.parse_args()
gold = [json.loads(line)["ner_tags"] for line in Path(args.gold).read_text(encoding="utf-8").splitlines() if line.strip()]
pred = [json.loads(line)["ner_tags"] for line in Path(args.predictions).read_text(encoding="utf-8").splitlines() if line.strip()]
if len(gold) != len(pred): raise SystemExit("Gold/prediction row counts differ.")
if not gold: raise SystemExit("Gold and prediction files contain no rows.")
metrics = entity_metrics(gold, pred); report = render_metrics(metrics)
Path(args.output).parent.mkdir(parents=True, exist_ok=True); Path(args.output).write_text(report, encoding="utf-8")
print(report)
