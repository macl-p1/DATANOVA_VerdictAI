from pathlib import Path


def test_extraction_code_never_emits_legal_flags():
    root = Path(__file__).resolve().parents[1] / "src" / "verdictai"
    extraction_sources = list((root / "models").glob("*.py")) + list((root / "inference").glob("*.py"))
    forbidden = ("PAST_HALF", "PAST_THIRD", "NOT_ELIGIBLE", "PAST_MAX")
    source = "\n".join(path.read_text(encoding="utf-8") for path in extraction_sources)
    assert not any(flag in source for flag in forbidden)
