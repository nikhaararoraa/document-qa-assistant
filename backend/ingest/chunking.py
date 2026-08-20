"""Docling chunking: a filing's Markdown -> retrieval-sized chunks with citation metadata.

Uses Docling's HybridChunker (hierarchical split + token-aware merge/split) over a
fresh DocumentConverter parse of the filing's Markdown. `chunk.meta.headings` and
page provenance are unusably empty on this corpus regardless of source format —
verified against a live 10-K (0/220 chunks had either, whether parsed from the
original HTML or the converted Markdown) — so `section` is derived independently via
a regex scan for "Item N." lines, and `page` is always None.
"""
from __future__ import annotations

import re
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling_core.transforms.serializer.markdown import MarkdownParams, MarkdownTableSerializer

MAX_CHUNK_TOKENS = 512

# SEC filings carry no page provenance through Docling on this corpus — see module docstring.
PAGE = None

_ITEM_SECTION_RE = re.compile(r"^item\s+\d+[a-z]?\..*$", re.MULTILINE | re.IGNORECASE)


class _MarkdownTableSerializerProvider(ChunkingSerializerProvider):
    """Keeps tables as clean per-chunk Markdown grids instead of compact/triplet cell text."""

    def get_serializer(self, doc: Any) -> ChunkingDocSerializer:
        return ChunkingDocSerializer(
            doc=doc,
            table_serializer=MarkdownTableSerializer(),
            params=MarkdownParams(compact_tables=True),
        )


def build_converter() -> DocumentConverter:
    return DocumentConverter()


def build_chunker() -> HybridChunker:
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.get_encoding("cl100k_base"), max_tokens=MAX_CHUNK_TOKENS
    )
    return HybridChunker(
        tokenizer=tokenizer,
        merge_peers=True,
        repeat_table_header=True,
        serializer_provider=_MarkdownTableSerializerProvider(),
    )


def chunk_markdown(
    markdown_text: str, converter: DocumentConverter, chunker: HybridChunker
) -> Iterator[Any]:
    """Runs a filing's Markdown through Docling + HybridChunker.

    DocumentConverter takes a path, not a raw string, so the text goes through a temp
    file first.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "filing.md"
        tmp_path.write_text(markdown_text, encoding="utf-8")
        doc = converter.convert(tmp_path).document
    yield from chunker.chunk(doc)


def _last_section_marker(text: str) -> str | None:
    """Returns the last "Item N. ..." line found in `text`, if any."""
    matches = _ITEM_SECTION_RE.findall(text)
    return matches[-1].strip() if matches else None


def build_chunk_row_fields(
    chunk: Any,
    chunker: HybridChunker,
    filing_metadata: dict,
    current_section: str | None,
) -> tuple[dict, str | None]:
    """Builds one `document_chunks` row's fields, plus the running current section.

    Chunks arrive in document reading order (guaranteed by HybridChunker), so section
    tracking only needs each chunk's *own* text checked for an "Item N." line -- if
    found, it becomes the new running section; otherwise the previous one carries
    forward. An earlier version tried to re-locate each chunk's reserialized text back
    inside the original Markdown by offset/substring search instead, but real SEC
    tables are full of near-empty filler cells (bare "|"/"-" tokens repeated across the
    whole filing), which made that search prone to false-positive matches deep inside
    an unrelated, later table. Scanning a chunk's own text has no such failure mode.
    """
    content = chunker.contextualize(chunk)
    marker = _last_section_marker(chunk.text)
    section = marker if marker is not None else current_section

    fields = {
        "content": content,
        "token_count": chunker.tokenizer.count_tokens(content),
        "page": PAGE,
        "section": section,
        "chunk_metadata": {
            **filing_metadata,
            "section": section,
            "page": PAGE,
            "headings": chunk.meta.headings or [],
            "doc_items": [item.self_ref for item in chunk.meta.doc_items],
            "raw_text": chunk.text,
        },
    }
    return fields, section
