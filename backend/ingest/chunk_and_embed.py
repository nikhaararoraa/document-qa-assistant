"""One-off ingestion: chunk `source_documents.content_markdown`, embed via local
Ollama, write `document_chunks`.

Usage (from backend/):
    uv run python -m ingest.chunk_and_embed --accession <id> --max-chunks 3 --dry-run
    uv run python -m ingest.chunk_and_embed --accession <id> --max-chunks 1
    uv run python -m ingest.chunk_and_embed --accession <id> --no-skip-existing
    uv run python -m ingest.chunk_and_embed --all
"""
from __future__ import annotations

import argparse

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import DocumentChunk, SourceDocument
from ingest import chunking, embeddings


def _filing_metadata(document: SourceDocument) -> dict:
    return {
        "ticker": document.ticker,
        "company_name": document.company_name,
        "filing_type": document.filing_type,
        "filing_date": document.filing_date.isoformat(),
        "report_date": document.report_date.isoformat(),
        "fiscal_year": document.fiscal_year,
        "accession_number": document.accession_number,
        "source_url": document.source_url,
    }


def chunk_and_embed_document(
    session: Session,
    document: SourceDocument,
    converter,
    chunker,
    max_chunks: int | None,
    dry_run: bool,
) -> int:
    """Chunks + embeds one filing and writes its `document_chunks` rows. Returns chunk count."""
    filing_metadata = _filing_metadata(document)

    rows: list[dict] = []
    current_section: str | None = None
    for chunk in chunking.chunk_markdown(document.content_markdown, converter, chunker):
        if max_chunks is not None and len(rows) >= max_chunks:
            break
        fields, current_section = chunking.build_chunk_row_fields(
            chunk, chunker, filing_metadata, current_section
        )
        rows.append(fields)

    if dry_run:
        print(f"[dry-run] {document.accession_number}: {len(rows)} chunks")
        for i, row in enumerate(rows):
            print(f"  chunk {i}: tokens={row['token_count']} section={row['section']!r}")
            print(f"    {row['content'][:200]!r}")
        return len(rows)

    embedded_vectors = embeddings.embed_texts([row["content"] for row in rows])

    session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    for index, (row, vector) in enumerate(zip(rows, embedded_vectors)):
        session.add(DocumentChunk(document_id=document.id, chunk_index=index, embedding=vector, **row))
    session.commit()
    print(f"{document.accession_number}: wrote {len(rows)} chunks")
    return len(rows)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accession", help="Process a single filing by accession number")
    parser.add_argument("--all", action="store_true", help="Process every source_documents row")
    parser.add_argument(
        "--max-chunks", type=int, default=None, help="Cap chunks written per document"
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip documents that already have document_chunks rows (default: on)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chunk + build metadata only; no Ollama calls, no DB writes",
    )
    args = parser.parse_args()
    if not args.accession and not args.all:
        parser.error("pass --accession <id> or --all")
    return args


def main() -> None:
    args = _parse_args()

    if not args.dry_run:
        embeddings.check_ollama_ready()

    engine = create_engine(settings.sqlalchemy_database_url)
    converter = chunking.build_converter()
    chunker = chunking.build_chunker()

    with Session(engine) as session:
        if args.accession:
            document = session.scalar(
                select(SourceDocument).where(SourceDocument.accession_number == args.accession)
            )
            if document is None:
                raise ValueError(f"No source_documents row for accession {args.accession!r}")
            documents = [document]
        else:
            documents = list(session.scalars(select(SourceDocument)))

        total = 0
        for document in documents:
            existing_count = session.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
            )
            if existing_count and args.skip_existing and not args.dry_run:
                print(f"Skipping {document.accession_number} (already has {existing_count} chunks)")
                continue
            total += chunk_and_embed_document(
                session, document, converter, chunker, args.max_chunks, args.dry_run
            )

    print(f"\nDone: {total} chunks {'previewed' if args.dry_run else 'written'}")


if __name__ == "__main__":
    main()
