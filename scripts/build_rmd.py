#!/usr/bin/env python3
"""Render the three .Rmd files (+ shared .tex includes) from a validated spec.

Layout produced under ``output_dir``:

    output_dir/
        _build/
            application/
                preamble.tex, header.tex, cover.tex, application.Rmd
            manual/
                preamble.tex, header.tex, cover.tex, manual.Rmd
            code/
                preamble.tex, header.tex, cover.tex, code.Rmd
        mockups/   (rendered separately by render_mockups.py)

The Rmd files reference ../../mockups/... for embedded images.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from template_rewriter import build_code_sections, load_spec  # noqa: E402


SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_DIR = SKILL_DIR / "templates" / "rmd"
PREAMBLE_FILE = TEMPLATE_DIR / "preamble.tex"


DOCUMENTS = ("application", "manual", "code")


def latex_escape(text: str) -> str:
    """Escape characters that have a special meaning in LaTeX."""
    if text is None:
        return ""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    out = str(text)
    for needle, sub in replacements:
        out = out.replace(needle, sub)
    return out


def r_string_vector(values: list[str]) -> str:
    """Render a Python list of strings as a comma-separated R character literal."""
    escaped = []
    for value in values:
        token = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
        escaped.append(f'"{token}"')
    return ", ".join(escaped)


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9一-鿿]+", "-", text).strip("-")
    return cleaned or "mod"


def _join_code(lines: list[str]) -> str:
    return "\n".join(lines)


def _module_figures(spec: dict, module_index: int) -> list[dict]:
    """Pick the mockup figures that belong to the given module (1-based)."""
    plan = spec["image_plan"]
    grouped: dict[int, list[dict]] = {}
    plan_iter = iter(plan)
    next(plan_iter)  # image1 is architecture; skip
    scenes_per_module = [2, 2, 3, 3, 2, 3]
    cursor = 0
    figures: list[dict] = []
    for idx, scenes_count in enumerate(scenes_per_module, start=1):
        bucket = []
        for _ in range(scenes_count):
            try:
                item = next(plan_iter)
            except StopIteration:
                break
            bucket.append(item)
        grouped[idx] = bucket
    return grouped.get(module_index, [])


def _build_manual_context(spec: dict, mockups_dir: str) -> dict:
    modules_ctx = []
    for idx, module in enumerate(spec["modules"], start=1):
        figures = _module_figures(spec, idx)
        modules_ctx.append({
            "title": module["title"],
            "summary": module["summary"],
            "groups": module["groups"],
            "slug": slugify(module["title"]),
            "figure_caption_index": idx,
            "figures": figures,
        })
    return {
        "software_name": spec["software_name"],
        "version": spec["version"],
        "intro": spec["intro"],
        "architecture_description": spec["architecture"]["description"],
        "flow_text": spec["flow_text"],
        "modules": modules_ctx,
        "mockups_dir": mockups_dir,
    }


def _build_application_context(spec: dict, source_line_count: int) -> dict:
    defaults = spec["defaults"]
    basic_rows = [
        ("权利取得方式", defaults["rights_acquisition"]),
        ("软件全称", spec["software_name"]),
        ("软件版本", spec["version"]),
        ("权利范围", defaults["rights_scope"]),
    ]
    attr_rows = [
        ("软件分类", defaults["software_type"]),
        ("软件说明", defaults["software_nature"]),
        ("开发方式", defaults["development_mode"]),
        ("开发完成日期", spec["development_date"]),
        ("发表状态", defaults["publication_status"]),
    ]
    tech_rows = [
        ("开发硬件环境", defaults["dev_hardware"]),
        ("运行硬件环境", defaults["run_hardware"]),
        ("开发操作系统", defaults["dev_os"]),
        ("开发工具", defaults["dev_tools"]),
        ("运行平台", defaults["run_platform"]),
        ("支撑软件", defaults["support_software"]),
        ("编程语言", defaults["languages"]),
        ("源程序总行数", str(source_line_count)),
        ("开发目的", spec["purpose"]),
        ("面向领域", f"面向{spec['industry']}领域，主要服务于{spec['target_users']}。"),
        ("主要功能", spec["main_features"]),
        ("技术特点", spec["technical_highlights"]),
    ]

    def escape_pair(rows):
        return [(latex_escape(k), latex_escape(v)) for k, v in rows]

    return {
        "software_name": spec["software_name"],
        "version": spec["version"],
        "basic_rows": escape_pair(basic_rows),
        "attr_rows": escape_pair(attr_rows),
        "tech_rows": escape_pair(tech_rows),
    }


def _build_code_context(spec: dict, sections: dict) -> dict:
    module_blocks = []
    for module in sections["modules"]:
        module_blocks.append({
            "title": module["title"],
            "code_block": _join_code(module["lines"]),
        })
    return {
        "software_name": spec["software_name"],
        "version": spec["version"],
        "bootstrap_code": _join_code(sections["bootstrap"]),
        "modules": module_blocks,
        "support_code": _join_code(sections["support"]) or "// no padding required",
    }


def _per_doc_includes(env: Environment, *, header_left: str, title: str, subtitle: str,
                     version: str, development_date: str) -> dict[str, str]:
    header = env.get_template("header.tex.j2").render(header_left=header_left)
    cover = env.get_template("cover.tex.j2").render(
        title_latex=latex_escape(title),
        subtitle_latex=latex_escape(subtitle),
        version=latex_escape(version),
        development_date=latex_escape(development_date),
    )
    return {"header.tex": header, "cover.tex": cover}


def build_rmd_tree(spec: dict, output_dir: Path, mockups_dir_rel: str = "../../mockups") -> dict:
    """Materialize the _build/{application,manual,code}/ tree. Returns paths."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    build_root = output_dir / "_build"
    build_root.mkdir(parents=True, exist_ok=True)

    code_sections = build_code_sections(spec)
    source_line_count = sum(
        1 for line in (
            list(code_sections["bootstrap"])
            + [line for module in code_sections["modules"] for line in module["lines"]]
            + list(code_sections["support"])
        )
        if line.strip()
    )

    common_includes = {
        "application": {
            "header_left": f"基于SpringBoot的{latex_escape(spec['software_name'])} {latex_escape(spec['version'])} 申请表",
            "title": f"基于SpringBoot的{spec['software_name']}",
            "subtitle": f"软件著作权申请表 {spec['version']}",
        },
        "manual": {
            "header_left": f"基于Java\\&Vue的{latex_escape(spec['software_name'])} {latex_escape(spec['version'])} 操作手册",
            "title": f"基于Java&Vue的{spec['software_name']}",
            "subtitle": f"操作手册 {spec['version']}",
        },
        "code": {
            "header_left": f"基于Java\\&Vue的{latex_escape(spec['software_name'])} {latex_escape(spec['version'])} 代码文档",
            "title": f"基于Java&Vue的{spec['software_name']}",
            "subtitle": f"代码文档 {spec['version']}",
        },
    }

    doc_contexts = {
        "application": _build_application_context(spec, source_line_count),
        "manual": _build_manual_context(spec, mockups_dir_rel),
        "code": _build_code_context(spec, code_sections),
    }

    rmd_paths: dict[str, Path] = {}
    for doc in DOCUMENTS:
        sub = build_root / doc
        sub.mkdir(parents=True, exist_ok=True)
        shutil.copy(PREAMBLE_FILE, sub / "preamble.tex")
        includes = _per_doc_includes(
            env,
            header_left=common_includes[doc]["header_left"],
            title=common_includes[doc]["title"],
            subtitle=common_includes[doc]["subtitle"],
            version=spec["version"],
            development_date=spec["development_date"],
        )
        for name, body in includes.items():
            (sub / name).write_text(body, encoding="utf-8")

        template = env.get_template(f"{doc}.Rmd.j2")
        rmd_body = template.render(**doc_contexts[doc])
        rmd_path = sub / f"{doc}.Rmd"
        rmd_path.write_text(rmd_body, encoding="utf-8")
        rmd_paths[doc] = rmd_path

    return {
        "build_root": build_root,
        "rmd_paths": rmd_paths,
        "source_line_count": source_line_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Rmd files from a validated spec.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mockups-dir", default="../../mockups",
                        help="Relative path from each Rmd to the mockups folder")
    args = parser.parse_args()

    spec = load_spec(Path(args.spec))
    result = build_rmd_tree(spec, Path(args.output_dir).resolve(), args.mockups_dir)
    summary = {
        "build_root": str(result["build_root"]),
        "rmd_paths": {k: str(v) for k, v in result["rmd_paths"].items()},
        "source_line_count": result["source_line_count"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
