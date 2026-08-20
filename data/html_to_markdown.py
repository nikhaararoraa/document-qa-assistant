# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "docling==2.118.1",
# ]
# ///
"""Convert downloaded SEC filing HTML into Markdown with docling.

Mirrors data/downloads/ (year folders + manifest.json) into data/markdown/,
one .md file per filing, so the corpus is ready for chunking/ingestion.

Usage:
    uv run data/html_to_markdown.py
"""
from __future__ import annotations

import json
from pathlib import Path

from docling.document_converter import DocumentConverter

DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"
OUTPUT_DIR = Path(__file__).resolve().parent / "markdown"
SKIP_EXISTING = True


def convert_filings() -> None:
    manifest = json.loads((DOWNLOADS_DIR / "manifest.json").read_text(encoding="utf-8"))
    converter = DocumentConverter()

    out_manifest = dict(manifest)
    out_manifest["filings"] = []
    converted = skipped = 0
    failed: list[str] = []

    total = len(manifest["filings"])
    for i, filing in enumerate(manifest["filings"], start=1):
        source_relative = Path(filing["local_path"].replace("\\", "/"))
        source_path = DOWNLOADS_DIR / source_relative
        target_relative = source_relative.with_suffix(".md")
        target_path = OUTPUT_DIR / target_relative
        target_path.parent.mkdir(parents=True, exist_ok=True)

        label = f"[{i}/{total}] {filing['ticker']} {filing['form']} {filing['filing_date']}"

        if SKIP_EXISTING and target_path.exists():
            print(f"{label} - skip (already converted)")
            skipped += 1
        else:
            print(f"{label} - converting {source_path.name}...")
            try:
                result = converter.convert(str(source_path))
                target_path.write_text(
                    result.document.export_to_markdown(), encoding="utf-8"
                )
                converted += 1
            except Exception as exc:  # noqa: BLE001 - keep batch going on per-file failures
                print(f"{label} - FAILED: {exc}")
                failed.append(str(source_relative))
                continue

        out_filing = dict(filing)
        out_filing["source_html_path"] = filing["local_path"]
        out_filing["local_path"] = str(target_relative)
        out_manifest["filings"].append(out_filing)

    out_manifest["downloaded_count"] = len(out_manifest["filings"])
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(out_manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nConverted {converted}, skipped {skipped}, failed {len(failed)}")
    if failed:
        print("Failed files:")
        for path in failed:
            print(f"  - {path}")


if __name__ == "__main__":
    convert_filings()
