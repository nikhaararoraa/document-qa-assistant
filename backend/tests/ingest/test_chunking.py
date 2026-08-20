"""Offline: real Docling conversion + HybridChunker over a synthetic Markdown fixture.

No network, no DB, no Ollama — only exercises `ingest.chunking`, which is pure/local.
"""

import pytest

from ingest import chunking

# Paragraphs are single unwrapped lines (not hand-wrapped at ~80 cols) -- Docling joins
# doc-items with a single "\n" when it reserializes chunk text, which doesn't always
# match hand-wrapped source spacing. Padded well past the chunker's 512-token budget
# so it's forced to split into multiple chunks under the same settings production uses.
_RISK_PARAGRAPH = (
    "Our business is subject to numerous risks and uncertainties, including competition, "
    "regulation, and supply chain risk in the technology sector. Adverse changes in any of "
    "these areas could materially affect our revenue, margins, and ability to execute our "
    "strategy across the regions in which we operate, and management continues to monitor "
    "these risks closely as part of the ongoing enterprise risk management program."
)
_MDA_PARAGRAPH = (
    "The following discussion should be read in conjunction with our consolidated financial "
    "statements and provides additional context on our recent operating performance and "
    "liquidity position, including trends in revenue recognition, cost of sales, and capital "
    "allocation that management believes are relevant to understanding the period-over-period "
    "changes presented elsewhere in this report."
)

# A noisy cover-page table (bare "|"/"-" filler cells, no real words) placed *before*
# any "Item N." marker -- this is what real SEC filings look like ahead of Item 1, and
# is a regression fixture for a real bug: an earlier offset-matching implementation of
# `build_chunk_row_fields` mismatched this kind of content against a much later table
# purely because both are full of near-identical "|"/"-" filler tokens.
_COVER_PAGE = "|  |  |  |\n| - | - | - |\n|  |  |  |\nFORM 10-K\n|  |  |  |\n| - | - | - |\n\n"

SAMPLE_MARKDOWN = (
    _COVER_PAGE
    + "Item 1A. Risk Factors\n\n"
    + (_RISK_PARAGRAPH + "\n\n") * 6
    + "| Region | FY2024 | FY2023 |\n| --- | --- | --- |\n| Americas | 100 | 90 |\n| Europe | 50 | 45 |\n\n"
    + "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS\n\n"
    + (_MDA_PARAGRAPH + "\n\n") * 6
)


def _all_chunks():
    converter = chunking.build_converter()
    chunker = chunking.build_chunker()
    return list(chunking.chunk_markdown(SAMPLE_MARKDOWN, converter, chunker)), chunker


class TestChunkMarkdown:
    def test_produces_multiple_chunks(self):
        chunks, _ = _all_chunks()
        assert len(chunks) >= 2

    def test_table_renders_as_markdown_grid_not_triplets(self):
        chunks, chunker = _all_chunks()
        table_chunk = next(c for c in chunks if "Americas" in c.text)
        assert "| Region" in table_chunk.text
        assert "100" in table_chunk.text and "90" in table_chunk.text


class TestLastSectionMarker:
    def test_finds_title_case_and_all_caps_markers(self):
        assert chunking._last_section_marker("Item 1A. Risk Factors").lower().startswith(
            "item 1a."
        )
        assert chunking._last_section_marker(
            "ITEM 7. MANAGEMENT'S DISCUSSION"
        ).lower().startswith("item 7.")

    def test_returns_last_when_multiple_markers_present(self):
        text = "Item 6. [Reserved]\n\nItem 7. Management's Discussion"
        assert chunking._last_section_marker(text).lower().startswith("item 7.")

    def test_no_marker_returns_none(self):
        assert chunking._last_section_marker("Just a plain paragraph, no item headers.") is None

    def test_table_filler_tokens_never_look_like_a_marker(self):
        assert chunking._last_section_marker(_COVER_PAGE) is None


class TestBuildChunkRowFields:
    """Exactly which chunk a table/paragraph lands in is `merge_peers`' call, not
    something these tests control -- e.g. a small table can end up bundled with the
    *next* section's heading rather than the previous one's, which is legitimate
    Docling behavior. So assertions here are written to hold regardless of exact
    chunk boundaries: single-marker fixtures for deterministic section values, and a
    monotonicity check (never reverts to an earlier section once a later one starts)
    for the multi-section fixture, rather than asserting a specific chunk's section.
    """

    def _rows(self, chunker, chunks, filing_metadata=None):
        rows = []
        current_section = None
        for chunk in chunks:
            fields, current_section = chunking.build_chunk_row_fields(
                chunk, chunker, filing_metadata or {}, current_section
            )
            rows.append(fields)
        return rows

    def test_shape(self):
        chunks, chunker = _all_chunks()
        filing_metadata = {"ticker": "TEST", "accession_number": "0000000000-00-000000"}
        rows = self._rows(chunker, chunks, filing_metadata)

        for row in rows:
            assert row.keys() == {"content", "token_count", "page", "section", "chunk_metadata"}
            assert row["page"] is None
            assert row["token_count"] > 0
            assert row["chunk_metadata"]["ticker"] == "TEST"
            assert row["chunk_metadata"]["raw_text"]
            assert row["chunk_metadata"]["page"] is None

    def test_no_marker_anywhere_in_document_means_every_row_has_no_section(self):
        """Regression fixture for a real bug: an earlier offset-matching implementation
        mismatched noisy cover-page table filler ("|"/"-" tokens) against an unrelated,
        much later table purely because both are full of near-identical filler tokens.
        """
        converter = chunking.build_converter()
        chunker = chunking.build_chunker()
        chunks = list(chunking.chunk_markdown(_COVER_PAGE * 3, converter, chunker))
        rows = self._rows(chunker, chunks)
        assert rows  # sanity: the fixture actually produced chunks
        assert all(row["section"] is None for row in rows)

    def test_single_marker_document_labels_every_row_with_it(self):
        single_section_markdown = (
            _COVER_PAGE + "Item 1A. Risk Factors\n\n" + (_RISK_PARAGRAPH + "\n\n") * 6
        )
        converter = chunking.build_converter()
        chunker = chunking.build_chunker()
        chunks = list(chunking.chunk_markdown(single_section_markdown, converter, chunker))
        rows = self._rows(chunker, chunks)
        assert rows
        assert all(row["section"] is not None for row in rows)
        assert all(row["section"].lower().startswith("item 1a.") for row in rows)

    def test_section_never_reverts_to_an_earlier_one_across_the_document(self):
        chunks, chunker = _all_chunks()
        rows = self._rows(chunker, chunks)
        sections_seen = [row["section"] for row in rows if row["section"] is not None]
        # every row is either still None (before Item 1A) or Item 1A, until the first
        # Item 7 row appears, after which it's Item 7 for the rest of the document.
        seen_item_7 = False
        for section in sections_seen:
            if section.lower().startswith("item 7."):
                seen_item_7 = True
            elif seen_item_7:
                pytest.fail(f"section reverted to {section!r} after Item 7 had started")
        assert seen_item_7, "fixture should reach Item 7 by the end"

    def test_content_is_contextualized_with_heading_or_falls_back_cleanly(self):
        chunks, chunker = _all_chunks()
        for row, chunk in zip(self._rows(chunker, chunks), chunks):
            # contextualize() never returns less than the raw chunk text.
            assert len(row["content"]) >= len(chunk.text)
