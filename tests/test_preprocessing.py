from verdictai.preprocessing.text_cleaner import normalize_text
from verdictai.preprocessing.tokenizer import tokenize_with_offsets


def test_preserves_legal_punctuation_and_dates():
    text = normalize_text("Sec. 303/304\u00a0 15.01.2024")
    assert "303/304" in text and "15.01.2024" in text
    assert tokenize_with_offsets(text)[0][0] == "Sec"
