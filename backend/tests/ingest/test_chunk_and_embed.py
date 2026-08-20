"""Offline: `ingest.chunking` and `ingest.embeddings` are mocked at the module
boundary (per backend/AGENTS.md's "mock at the service boundary"). No real Docling
conversion, no Ollama, no DB — `document_chunks`/`document_chunks.embedding` use
Postgres-only types (pgvector, JSONB, generated TSVECTOR), so a real session isn't
viable in the fast/offline suite; a lightweight fake session records calls instead.
"""
import sys
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.database.models import DocumentChunk, SourceDocument
from ingest import chunk_and_embed, chunking, embeddings


def _make_document(**overrides) -> SourceDocument:
    fields = {
        "id": uuid4(),
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "cik": "0000320193",
        "filing_type": "10-K",
        "filing_date": date(2025, 10, 31),
        "report_date": date(2025, 9, 27),
        "fiscal_year": 2025,
        "accession_number": "0000320193-25-000079",
        "source_url": "https://example.com/aapl.htm",
        "content_markdown": "Item 1A. Risk Factors\n\nSome risk text.",
    }
    fields.update(overrides)
    return SourceDocument(**fields)


class _FakeSession:
    """Records `.execute()`/`.add()`/`.commit()` calls without touching a real DB."""

    def __init__(self):
        self.executed = []
        self.added = []
        self.commits = 0

    def execute(self, statement):
        self.executed.append(statement)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


@pytest.fixture(autouse=True)
def _mock_chunking_and_embeddings(monkeypatch: pytest.MonkeyPatch):
    """Stubs the real Docling/Ollama calls with deterministic fakes."""

    def fake_chunk_markdown(markdown_text, converter, chunker):
        for i in range(3):
            yield SimpleNamespace(text=f"chunk {i} text")

    def fake_build_chunk_row_fields(chunk, chunker, filing_metadata, current_section):
        fields = {
            "content": chunk.text,
            "token_count": 10,
            "page": None,
            "section": "Item 1A. Risk Factors",
            "chunk_metadata": {**filing_metadata, "raw_text": chunk.text},
        }
        return fields, fields["section"]

    monkeypatch.setattr(chunking, "chunk_markdown", fake_chunk_markdown)
    monkeypatch.setattr(chunking, "build_chunk_row_fields", fake_build_chunk_row_fields)
    monkeypatch.setattr(
        embeddings, "embed_texts", lambda texts: [[0.1, 0.2, 0.3, 0.4] for _ in texts]
    )


class TestChunkAndEmbedDocument:
    def test_dry_run_makes_no_embedding_or_db_calls(self, monkeypatch: pytest.MonkeyPatch):
        calls = []
        monkeypatch.setattr(
            embeddings, "embed_texts", lambda texts: calls.append(texts) or []
        )
        session = _FakeSession()
        document = _make_document()

        count = chunk_and_embed.chunk_and_embed_document(
            session, document, converter=None, chunker=None, max_chunks=None, dry_run=True
        )

        assert count == 3
        assert calls == []
        assert session.added == []
        assert session.executed == []
        assert session.commits == 0

    def test_max_chunks_truncates(self):
        session = _FakeSession()
        document = _make_document()

        count = chunk_and_embed.chunk_and_embed_document(
            session, document, converter=None, chunker=None, max_chunks=1, dry_run=False
        )

        assert count == 1
        assert len(session.added) == 1

    def test_writes_rows_with_sequential_chunk_index_and_deletes_first(self):
        session = _FakeSession()
        document = _make_document()

        chunk_and_embed.chunk_and_embed_document(
            session, document, converter=None, chunker=None, max_chunks=None, dry_run=False
        )

        assert len(session.executed) == 1  # the delete-existing-chunks statement
        assert len(session.added) == 3
        assert [row.chunk_index for row in session.added] == [0, 1, 2]
        assert all(row.document_id == document.id for row in session.added)
        assert all(row.embedding == [0.1, 0.2, 0.3, 0.4] for row in session.added)
        assert session.commits == 1


class TestParseArgs:
    def test_requires_accession_or_all(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(sys, "argv", ["chunk_and_embed"])
        with pytest.raises(SystemExit):
            chunk_and_embed._parse_args()

    def test_skip_existing_defaults_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(sys, "argv", ["chunk_and_embed", "--all"])
        args = chunk_and_embed._parse_args()
        assert args.skip_existing is True

    def test_no_skip_existing_flag(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(sys, "argv", ["chunk_and_embed", "--all", "--no-skip-existing"])
        args = chunk_and_embed._parse_args()
        assert args.skip_existing is False

    def test_max_chunks_parsed_as_int(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            sys, "argv", ["chunk_and_embed", "--accession", "0000320193-25-000079", "--max-chunks", "1"]
        )
        args = chunk_and_embed._parse_args()
        assert args.max_chunks == 1
