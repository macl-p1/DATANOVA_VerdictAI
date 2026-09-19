#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.labels import entity_types, load_labels
from verdictai.data.validation import validate_directory

parser = argparse.ArgumentParser(description="Validate canonical VerdictAI annotations.")
parser.add_argument("--input", default="data/annotations")
parser.add_argument("--labels", default="configs/labels.yaml")
parser.add_argument("--max-characters", type=int, default=250000)
args = parser.parse_args()
report = validate_directory(args.input, entity_types(load_labels(args.labels)), args.max_characters)
print(report.render())
raise SystemExit(0 if report.valid else 1)
