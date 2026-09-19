from verdictai.api import create_app


def test_api_registers_interface_and_health_routes(monkeypatch, tmp_path):
    class DummyTokenizer:
        pass

    class DummyModel:
        pass

    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", lambda *_: DummyTokenizer())
    monkeypatch.setattr("transformers.AutoModelForTokenClassification.from_pretrained", lambda *_: DummyModel())
    app = create_app(str(tmp_path))
    assert any(route.path == "/" for route in app.routes)
    assert any(route.path == "/review-public-case" for route in app.routes)
    health = next(route.endpoint for route in app.routes if route.path == "/health")
    assert health()["predict_endpoint"] == "POST /predict"
