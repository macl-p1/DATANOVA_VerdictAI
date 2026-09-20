"""Test bootstrap.

At runtime the contents of `shared/` are published as a Lambda layer and land
on sys.path as top-level modules, so the functions import `schemas` and
`http_utils` directly. Locally there is no layer, so the same path is arranged
here and the environment variables the handlers read at import time are given
harmless defaults.
"""
import os
import sys
from pathlib import Path

SHARED = Path(__file__).parent / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault("STATUTES_TABLE", "test-statutes")
os.environ.setdefault("CASES_TABLE", "test-cases")
os.environ.setdefault("UPLOAD_BUCKET", "test-bucket")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
