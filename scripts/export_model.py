#!/usr/bin/env python
"""Copy an already saved safe Transformers checkpoint to an export directory."""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
source, output = Path(args.model), Path(args.output)
required = {"config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "label_map.json", "model_metadata.json"}
missing = [name for name in required if not (source / name).exists()]
if missing: raise SystemExit(f"Refusing export; missing required safe files: {', '.join(missing)}")
output.mkdir(parents=True, exist_ok=True)
for name in required: shutil.copy2(source / name, output / name)
print(f"Exported {len(required)} files to {output}")
