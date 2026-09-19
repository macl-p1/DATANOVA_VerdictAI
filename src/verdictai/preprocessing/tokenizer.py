"""Word tokenisation retaining legal punctuation and source offsets."""
from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"\w+(?:[./-]\w+)*|[^\w\s]", re.UNICODE)


def tokenize_with_offsets(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(), match.start(), match.end()) for match in TOKEN_PATTERN.finditer(text)]
