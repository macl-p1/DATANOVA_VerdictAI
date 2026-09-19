#!/usr/bin/env python
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.data.dataset import load_documents
from verdictai.data.splits import split_documents

parser = argparse.ArgumentParser(description="Create document/group-level splits.")
parser.add_argument("--input", default="data/annotations")
parser.add_argument("--output", default="data/processed")
parser.add_argument("--seed", type=int, default=42)
args = parser.parse_args()
output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
for name, documents in split_documents(load_documents(args.input), args.seed).items():
    with (output / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
        for document in documents: handle.write(document.model_dump_json() + "\n")
    print(f"{name}: {len(documents)} documents")
