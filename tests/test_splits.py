import pytest
from verdictai.data.splits import assert_no_leakage, split_documents
from verdictai.schemas import LegalDocument


def doc(identifier, case):
    return LegalDocument(document_id=identifier, case_group_id=case, pages=[{"page": 1, "text": identifier}])


def test_leakage():
    with pytest.raises(ValueError, match="case group"):
        assert_no_leakage({"train": [doc("a", "same")], "test": [doc("b", "same")]})


def test_split_rejects_non_positive_ratios():
    with pytest.raises(ValueError, match="positive"):
        split_documents([doc("a", "a")], ratios=(1.0, 0.0, 0.0))
