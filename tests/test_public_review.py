from verdictai.api import PublicCaseReviewRequest


def test_public_review_accepts_local_text_without_a_url():
    request = PublicCaseReviewRequest(
        document_id="LOCAL_CASE",
        text="Arrest date: 15 January 2024.",
        case_title="Local case notes",
        source_label="Local file: notes.txt",
    )
    assert request.source_url is None
    assert request.source_label == "Local file: notes.txt"
