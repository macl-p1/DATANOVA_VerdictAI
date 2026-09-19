import json
from verdictai.data.dataset import document_to_token_rows
from verdictai.data.validation import validate_directory
from verdictai.labels import entity_types, load_labels
from verdictai.schemas import LegalDocument


def document():
    text = "The accused was arrested on 15 January 2024."
    return {"document_id": "CASE_1", "language": "en", "source_type": "synthetic", "pages": [{"page": 1, "text": text}], "entities": [{"type": "ARREST_DATE", "text": "15 January 2024", "page": 1, "start": 28, "end": 43}]}


def test_bio_conversion():
    row = document_to_token_rows(LegalDocument.model_validate(document()))[0]
    assert row["ner_tags"][-4:] == ["B-ARREST_DATE", "I-ARREST_DATE", "I-ARREST_DATE", "O"]


def test_invalid_span(tmp_path):
    payload = document(); payload["entities"][0]["end"] = 99
    (tmp_path / "x.json").write_text(json.dumps(payload), encoding="utf-8")
    report = validate_directory(tmp_path, entity_types(load_labels()))
    assert not report.valid and any("invalid span" in error for error in report.errors)


def test_duplicate_document(tmp_path):
    for name in ("x", "y"):
        payload = document(); payload["document_id"] = name
        (tmp_path / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")
    report = validate_directory(tmp_path, entity_types(load_labels()))
    assert not report.valid and report.duplicate_documents == 1


def test_invalid_label(tmp_path):
    payload = document(); payload["entities"][0]["type"] = "RELEASE_ELIGIBILITY"
    (tmp_path / "x.json").write_text(json.dumps(payload), encoding="utf-8")
    assert not validate_directory(tmp_path, entity_types(load_labels())).valid


def test_duplicate_page_numbers_are_rejected(tmp_path):
    payload = document()
    payload["pages"].append({"page": 1, "text": "A second page with the same number."})
    (tmp_path / "x.json").write_text(json.dumps(payload), encoding="utf-8")
    report = validate_directory(tmp_path, entity_types(load_labels()))
    assert not report.valid and any("duplicate page numbers" in error for error in report.errors)
