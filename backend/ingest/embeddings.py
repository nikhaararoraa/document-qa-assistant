"""Local embedding generation via Ollama.

Not OpenAI — see docs/guides/todo.md Phase 4 notes. Calls Ollama's batch embedding
endpoint over plain httpx; no new dependency, httpx is already a runtime dependency.
"""
from __future__ import annotations

import httpx

from app.config import settings

BATCH_SIZE = 50


class OllamaNotReadyError(RuntimeError):
    pass


def check_ollama_ready() -> None:
    """Fails fast with a clear message if Ollama isn't reachable or the model isn't pulled."""
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OllamaNotReadyError(
            f"Ollama not reachable at {settings.ollama_base_url} — is it running? "
            "Start it with `ollama serve`."
        ) from exc

    pulled_models = {
        model["model"].split(":")[0] for model in response.json().get("models", [])
    }
    if settings.embedding_model not in pulled_models:
        raise OllamaNotReadyError(
            f"Model '{settings.embedding_model}' not found in Ollama — "
            f"run `ollama pull {settings.embedding_model}`."
        )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds `texts` in batches via Ollama, preserving input order."""
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        response = httpx.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": settings.embedding_model, "input": batch},
            timeout=120,
        )
        response.raise_for_status()
        batch_embeddings = response.json()["embeddings"]
        for embedding in batch_embeddings:
            if len(embedding) != settings.embedding_dimensions:
                raise ValueError(
                    f"Expected {settings.embedding_dimensions}-dim embedding from "
                    f"'{settings.embedding_model}', got {len(embedding)}"
                )
        embeddings.extend(batch_embeddings)
    return embeddings
