#!/usr/bin/env python
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from verdictai.api import create_app
parser = argparse.ArgumentParser(); parser.add_argument("--model", default="artifacts/models/verdictai-indicbert"); parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()
import uvicorn
uvicorn.run(create_app(args.model), host="127.0.0.1", port=args.port)
