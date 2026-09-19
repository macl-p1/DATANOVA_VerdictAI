#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.data.dataset import load_documents, write_token_dataset
from verdictai.data.validation import validate_directory
from verdictai.labels import entity_types, load_labels

parser = argparse.ArgumentParser(description="Convert validated annotations to token-level JSONL.")
parser.add_argument("--input", default="data/annotations")
parser.add_argument("--output", default="data/processed/tokens.jsonl")
args = parser.parse_args()
report = validate_directory(args.input, entity_types(load_labels()))
if not report.valid:
    print(report.render()); raise SystemExit(1)
print(f"Wrote {write_token_dataset(load_documents(args.input), args.output)} page rows to {args.output}")
