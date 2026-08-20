"""Offline: httpx is monkeypatched, no real Ollama server is contacted."""

import httpx
import pytest

from app.config import settings
from ingest import embeddings


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


@pytest.fixture(autouse=True)
def _fixed_embedding_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "embedding_model", "nomic-embed-text")
    monkeypatch.setattr(settings, "embedding_dimensions", 4)


class TestCheckOllamaReady:
    def test_raises_when_server_unreachable(self, monkeypatch: pytest.MonkeyPatch):
        def fake_get(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "get", fake_get)

        with pytest.raises(embeddings.OllamaNotReadyError, match="ollama serve"):
            embeddings.check_ollama_ready()

    def test_raises_when_model_not_pulled(self, monkeypatch: pytest.MonkeyPatch):
        def fake_get(*args, **kwargs):
            return _FakeResponse({"models": [{"model": "llama3:latest"}]})

        monkeypatch.setattr(httpx, "get", fake_get)

        with pytest.raises(embeddings.OllamaNotReadyError, match="ollama pull nomic-embed-text"):
            embeddings.check_ollama_ready()

    def test_passes_when_model_pulled(self, monkeypatch: pytest.MonkeyPatch):
        def fake_get(*args, **kwargs):
            return _FakeResponse({"models": [{"model": "nomic-embed-text:latest"}]})

        monkeypatch.setattr(httpx, "get", fake_get)

        embeddings.check_ollama_ready()  # must not raise


class TestEmbedTexts:
    def test_batches_requests_and_preserves_order(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(embeddings, "BATCH_SIZE", 2)
        calls = []

        def fake_post(url, json, timeout):
            calls.append(json["input"])
            return _FakeResponse({"embeddings": [[0.1, 0.2, 0.3, 0.4] for _ in json["input"]]})

        monkeypatch.setattr(httpx, "post", fake_post)

        texts = ["a", "b", "c", "d", "e"]
        result = embeddings.embed_texts(texts)

        assert len(calls) == 3  # ceil(5 / 2)
        assert calls == [["a", "b"], ["c", "d"], ["e"]]
        assert len(result) == 5
        assert all(len(vec) == 4 for vec in result)

    def test_raises_on_dimension_mismatch(self, monkeypatch: pytest.MonkeyPatch):
        def fake_post(url, json, timeout):
            return _FakeResponse({"embeddings": [[0.1, 0.2]]})  # wrong dim (expects 4)

        monkeypatch.setattr(httpx, "post", fake_post)

        with pytest.raises(ValueError, match="Expected 4-dim"):
            embeddings.embed_texts(["only text"])
