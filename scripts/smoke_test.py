#!/usr/bin/env python3
"""
Smoke test: validate the spec fixture and assemble a full bundle.

The fixture lives at assets/fixtures/sample_spec.json and stands in for what
the calling LLM would normally produce. The script layer does not generate
content on its own; this test only verifies the validate + assemble path.
"""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_bundle import render_bundle  # noqa: E402
from template_rewriter import load_spec  # noqa: E402


FIXTURE = SCRIPT_DIR.parent / "assets" / "fixtures" / "sample_spec.json"


def count_media(docx_path: Path) -> int:
    with zipfile.ZipFile(docx_path) as archive:
        return len([
            name for name in archive.namelist()
            if name.startswith("word/media/") and not name.endswith("/")
        ])


def main() -> None:
    spec = load_spec(FIXTURE)
    with tempfile.TemporaryDirectory(prefix="softcopy-smoke-") as temp_dir:
        output_dir = Path(temp_dir)
        result = render_bundle(spec, output_dir)

        required_files = [
            Path(result["spec_path"]),
            Path(result["application_path"]),
            Path(result["manual_path"]),
            Path(result["code_path"]),
        ]
        for path in required_files:
            if not path.exists():
                raise FileNotFoundError(f"Missing generated file: {path}")

        mockup_files = sorted(Path(result["mockup_dir"]).glob("*.*"))
        if len(mockup_files) != 16:
            raise RuntimeError(f"Expected 16 mockups, got {len(mockup_files)}")

        if result["source_line_count"] < 3200:
            raise RuntimeError(
                f"Expected at least 3200 non-empty code lines, got {result['source_line_count']}"
            )

        manual_media = count_media(Path(result["manual_path"]))
        if manual_media != 16:
            raise RuntimeError(f"Expected 16 embedded manual images, got {manual_media}")

        print(json.dumps({
            "ok": True,
            "fixture": str(FIXTURE.name),
            "generated_files": [path.name for path in required_files],
            "mockup_count": len(mockup_files),
            "manual_media": manual_media,
            "source_line_count": result["source_line_count"],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
