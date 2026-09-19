from verdictai.models.postprocessing import merge_bio_predictions, normalize_date


def test_normalize_date():
    assert normalize_date("15.01.2024") == "2024-01-15"


def test_merge_bio_entities_and_deduplicate():
    predictions = [
        {"label": "B-LEGAL_SECTION", "text": "Section", "start": 0, "end": 7, "confidence": .9},
        {"label": "I-LEGAL_SECTION", "text": "303", "start": 8, "end": 11, "confidence": .8},
    ]
    entities = merge_bio_predictions(predictions, "CASE_1", 1)
    assert len(entities) == 1
    assert entities[0].value == "Section 303"
    assert entities[0].evidence.document_id == "CASE_1"
