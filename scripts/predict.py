#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.config import load_config
from verdictai.inference.pipeline import predict_text

parser = argparse.ArgumentParser(description="Extract facts; never make a legal decision.")
parser.add_argument("--model", default="artifacts/models/verdictai-indicbert")
parser.add_argument("--input", required=True)
parser.add_argument("--document-id", default=None)
parser.add_argument("--config", default="configs/inference.yaml")
args = parser.parse_args()
if Path(args.input).suffix.lower() == ".pdf": raise SystemExit("PDF input needs an OCR adapter; provide OCR text to avoid silent extraction failure.")
from transformers import AutoModelForTokenClassification, AutoTokenizer
config = load_config(args.config); text = Path(args.input).read_text(encoding="utf-8")
model_path = Path(args.model)
if not model_path.is_dir():
    raise SystemExit(f"Local model directory not found: {model_path}. Train a model first, or pass an existing local checkpoint directory.")
tokenizer = AutoTokenizer.from_pretrained(str(model_path)); model = AutoModelForTokenClassification.from_pretrained(str(model_path))
result = predict_text(model, tokenizer, text, args.document_id or Path(args.input).stem, config["confidence"]["review_below"], config["data"]["max_length"], config["data"]["stride"])
print(result.model_dump_json(indent=2))
