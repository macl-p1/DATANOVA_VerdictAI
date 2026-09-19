from verdictai.inference.confidence import review_reasons
from verdictai.schemas import Evidence, ExtractedEntity


def test_low_confidence_requires_review():
    entity = ExtractedEntity(type="ARREST_DATE", value="15.01.2024", evidence=Evidence(document_id="C", text="15.01.2024", confidence=.60))
    assert review_reasons([entity], .70)
