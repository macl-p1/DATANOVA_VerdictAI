from verdictai.config import load_config


def test_load_config_accepts_parent_name_with_extension(tmp_path):
    (tmp_path / "base.yaml").write_text("model:\n  name: base\n", encoding="utf-8")
    (tmp_path / "child.yaml").write_text("extends: base.yaml\nmodel:\n  revision: abc\n", encoding="utf-8")
    assert load_config(tmp_path / "child.yaml") == {"model": {"name": "base", "revision": "abc"}}


def test_load_config_accepts_parent_name_without_extension(tmp_path):
    (tmp_path / "base.yaml").write_text("model:\n  name: base\n", encoding="utf-8")
    (tmp_path / "child.yaml").write_text("extends: base\n", encoding="utf-8")
    assert load_config(tmp_path / "child.yaml") == {"model": {"name": "base"}}
