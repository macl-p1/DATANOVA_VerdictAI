import pytest

from verdictai.evaluation.metrics import entity_metrics


def test_metrics_reject_misaligned_sequence_counts():
    with pytest.raises(ValueError, match="sequence counts"):
        entity_metrics([["O"]], [])


def test_metrics_reject_misaligned_token_counts():
    with pytest.raises(ValueError, match="token counts"):
        entity_metrics([["O", "O"]], [["O"]])
