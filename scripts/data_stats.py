#!/usr/bin/env python
from __future__ import annotations
import argparse
import collections
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.data.dataset import load_documents

parser = argparse.ArgumentParser(description="Report real dataset counts; never fabricates data.")
parser.add_argument("--input", default="data/annotations")
args = parser.parse_args()
documents = load_documents(args.input)
print(f"Documents: {len(documents)}")
print("Entities:", dict(collections.Counter(entity.type for document in documents for entity in document.entities)))
print("Languages:", dict(collections.Counter(document.language for document in documents)))
print("Sources:", dict(collections.Counter(document.source_type for document in documents)))
