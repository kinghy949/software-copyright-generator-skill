#!/usr/bin/env python3
"""End-to-end PDF bundle renderer.

Steps:
  1. Load + validate spec.json
  2. Render 16 mockup images
  3. Build .Rmd tree under output_dir/_build/
  4. Invoke Rscript -e 'rmarkdown::render(...)' per document
  5. Copy/rename the resulting PDFs to output_dir/<friendly-name>.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_rmd import build_rmd_tree  # noqa: E402
from render_mockups import render_mockups  # noqa: E402
from template_rewriter import load_spec, safe_filename  # noqa: E402


def _augmented_env() -> dict:
    """Make TinyTeX binaries discoverable when xelatex isn't on the default PATH."""
    env = os.environ.copy()
    candidates = [
        Path.home() / "Library" / "TinyTeX" / "bin" / "universal-darwin",
        Path.home() / ".TinyTeX" / "bin" / "x86_64-linux",
        Path.home() / ".TinyTeX" / "bin" / "aarch64-linux",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    extras = [str(p) for p in candidates if p.exists()]
    if extras:
        env["PATH"] = os.pathsep.join(extras + [env.get("PATH", "")])
    return env


def _render_one(rmd_path: Path) -> Path:
    cmd = [
        "Rscript", "-e",
        f"rmarkdown::render('{rmd_path.as_posix()}', quiet=TRUE)",
    ]
    subprocess.run(cmd, check=True, env=_augmented_env())
    pdf = rmd_path.with_suffix(".pdf")
    if not pdf.exists():
        raise RuntimeError(f"Rscript did not produce {pdf}")
    return pdf


def render_bundle(spec: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    mockup_dir = output_dir / "mockups"
    spec_path = output_dir / f"{safe_filename(spec['software_name'])}_spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    render_mockups(spec, mockup_dir)

    build_result = build_rmd_tree(spec, output_dir)

    pdfs: dict[str, Path] = {}
    for doc, rmd_path in build_result["rmd_paths"].items():
        pdfs[doc] = _render_one(rmd_path)

    file_stub = safe_filename(spec["software_name"])
    targets = {
        "application": output_dir / f"{file_stub}_申请表.pdf",
        "manual": output_dir / f"{file_stub}_操作手册.pdf",
        "code": output_dir / f"{file_stub}_代码文档.pdf",
    }
    if "genai_declaration" in pdfs:
        targets["genai_declaration"] = (
            output_dir / f"{file_stub}_合法合规及原创性声明文件.pdf"
        )
    for doc, target in targets.items():
        shutil.copy(pdfs[doc], target)

    result = {
        "spec_path": str(spec_path),
        "application_path": str(targets["application"]),
        "manual_path": str(targets["manual"]),
        "code_path": str(targets["code"]),
        "mockup_dir": str(mockup_dir),
        "build_root": str(build_result["build_root"]),
        "source_line_count": build_result["source_line_count"],
    }
    if "genai_declaration" in targets:
        result["genai_declaration_path"] = str(targets["genai_declaration"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the soft copyright PDF bundle.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    spec = load_spec(Path(args.spec))
    result = render_bundle(spec, Path(args.output_dir).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
