import pytest

from verdictai.api import create_app


def test_api_reports_missing_local_model_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="Local model directory not found"):
        create_app(str(tmp_path / "missing"))
