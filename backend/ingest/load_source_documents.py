"""One-off ingestion: load converted filing Markdown into `source_documents`.

Reads data/markdown/manifest.json (written by data/html_to_markdown.py) and
upserts one row per filing, keyed on the SEC accession number.

Usage (from backend/):
    uv run python -m ingest.load_source_documents
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import SourceDocument

MARKDOWN_DIR = Path(__file__).resolve().parents[2] / "data" / "markdown"

# True: leave rows that already exist untouched (fast re-runs).
# False: overwrite existing rows with the current Markdown/metadata.
SKIP_EXISTING = True

TICKER_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_source_documents() -> dict[str, int]:
    manifest = json.loads((MARKDOWN_DIR / "manifest.json").read_text(encoding="utf-8"))
    engine = create_engine(settings.sqlalchemy_database_url)
    counts = {"inserted": 0, "updated": 0, "skipped": 0}

    with Session(engine) as session:
        for filing in manifest["filings"]:
            accession_number = filing["accession_number"]
            existing = session.scalar(
                select(SourceDocument).where(SourceDocument.accession_number == accession_number)
            )

            if existing and SKIP_EXISTING:
                print(f"Skipping {accession_number} (already ingested)")
                counts["skipped"] += 1
                continue

            markdown_path = MARKDOWN_DIR / filing["local_path"].replace("\\", "/")
            report_date = _parse_date(filing["report_date"])
            fields = {
                "ticker": filing["ticker"],
                "company_name": TICKER_NAMES.get(filing["ticker"]),
                "cik": filing["cik"],
                "filing_type": filing["form"],
                "filing_date": _parse_date(filing["filing_date"]),
                "report_date": report_date,
                "fiscal_year": report_date.year,
                "accession_number": accession_number,
                "source_url": filing["source_url"],
                "content_markdown": markdown_path.read_text(encoding="utf-8"),
            }

            if existing:
                print(f"Updating {accession_number}...")
                for key, value in fields.items():
                    setattr(existing, key, value)
                counts["updated"] += 1
            else:
                print(f"Inserting {accession_number}...")
                session.add(SourceDocument(**fields))
                counts["inserted"] += 1

        session.commit()

    return counts


if __name__ == "__main__":
    result = load_source_documents()
    print(
        f"\nDone: {result['inserted']} inserted, "
        f"{result['updated']} updated, {result['skipped']} skipped"
    )
