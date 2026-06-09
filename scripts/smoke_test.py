#!/usr/bin/env python3
"""End-to-end smoke test: validate spec → render mockups → build Rmd → compile PDFs.

Uses ``assets/fixtures/sample_spec.json`` as a stand-in for what the calling LLM
would normally write.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pikepdf

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_pdf import render_bundle  # noqa: E402
from template_rewriter import load_spec  # noqa: E402


FIXTURE = SCRIPT_DIR.parent / "assets" / "fixtures" / "sample_spec.json"
MIN_PDF_BYTES = 50_000
MIN_CODE_PAGES = 40


def main() -> None:
    spec = load_spec(FIXTURE)
    with tempfile.TemporaryDirectory(prefix="softcopy-smoke-") as temp_dir:
        output_dir = Path(temp_dir)
        result = render_bundle(spec, output_dir)

        pdf_paths = {
            "application": Path(result["application_path"]),
            "manual": Path(result["manual_path"]),
            "code": Path(result["code_path"]),
        }
        for label, path in pdf_paths.items():
            if not path.exists():
                raise FileNotFoundError(f"Missing {label} PDF: {path}")
            if path.stat().st_size < MIN_PDF_BYTES:
                raise RuntimeError(f"{label} PDF too small: {path.stat().st_size} bytes")

        mockups = [p for p in sorted(Path(result["mockup_dir"]).glob("*.*"))
                   if p.suffix.lower() in {".png", ".jpeg", ".jpg"}]
        if not (8 <= len(mockups) <= 16):
            raise RuntimeError(f"Expected 8-16 mockups, got {len(mockups)}")

        if result["source_line_count"] < 3200:
            raise RuntimeError(
                f"Expected ≥3200 non-empty code lines, got {result['source_line_count']}"
            )

        with pikepdf.open(pdf_paths["manual"]) as pdf:
            manual_pages = len(pdf.pages)
            manual_outline = pdf.open_outline().root
            manual_bookmarks = len(manual_outline)
        with pikepdf.open(pdf_paths["code"]) as pdf:
            code_pages = len(pdf.pages)
            code_outline = pdf.open_outline().root
            code_bookmarks = len(code_outline)

        if manual_bookmarks < 1:
            raise RuntimeError("Manual PDF has no top-level outline bookmarks")
        if code_bookmarks < 6:
            raise RuntimeError(
                f"Code PDF should have ≥6 top-level bookmarks (one per module + appendix); got {code_bookmarks}"
            )
        if code_pages < MIN_CODE_PAGES:
            raise RuntimeError(f"Code PDF should be ≥{MIN_CODE_PAGES} pages, got {code_pages}")

        print(json.dumps({
            "ok": True,
            "fixture": FIXTURE.name,
            "manual_pages": manual_pages,
            "manual_bookmarks": manual_bookmarks,
            "code_pages": code_pages,
            "code_bookmarks": code_bookmarks,
            "source_line_count": result["source_line_count"],
            "mockup_count": len(mockups),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
