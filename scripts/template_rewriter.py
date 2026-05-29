#!/usr/bin/env python3
"""
Spec validation + structural assembly.

Content is provided by the invoking LLM via a spec.json that conforms to the
schema documented in SKILL.md. This module:

  - validate_spec(spec): raise SpecError with a clear message if any field
    violates length / cardinality constraints.
  - build_manual_sequence(spec): flatten the spec into the ordered list of
    paragraphs that replace placeholders in template_manual.docx.
  - build_code_lines(spec, min_non_empty_lines): flatten module code snippets
    and pad with placeholder support classes until the minimum line count is
    reached.
  - build_image_plan(spec): derive the 16-image plan from module titles.

No hardcoded business content lives here. If a field is missing the script
errors out and the caller (LLM) is expected to retry.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


REQUIRED_TOP_FIELDS = [
    "software_name", "version", "subject", "industry", "target_users",
    "intro", "purpose", "main_features", "technical_highlights",
    "flow_text", "architecture", "modules", "defaults",
    "development_date", "package_name", "class_prefix",
]

REQUIRED_DEFAULTS = [
    "rights_acquisition", "rights_scope", "software_type", "software_nature",
    "development_mode", "publication_status", "dev_hardware", "run_hardware",
    "dev_os", "dev_tools", "run_platform", "support_software", "languages",
]

MODULE_COUNT = 6
GROUPS_PER_MODULE_MIN = 2
GROUPS_PER_MODULE_MAX = 4
STEPS_PER_GROUP_MIN = 2
STEPS_PER_GROUP_MAX = 5
PURPOSE_MAX = 50
MAIN_FEATURES_MIN = 500
MAIN_FEATURES_MAX = 1300
INTRO_MAX = 140
ARCHITECTURE_LAYERS_MIN = 4
ARCHITECTURE_LAYERS_MAX = 6


class SpecError(ValueError):
    """Raised when the model-provided spec fails validation."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SpecError(message)


def _is_str(value, *, min_len: int = 1, max_len: int | None = None) -> bool:
    if not isinstance(value, str) or len(value) < min_len:
        return False
    if max_len is not None and len(value) > max_len:
        return False
    return True


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", text or "").strip() or "未命名系统"


def validate_spec(spec: dict) -> None:
    _require(isinstance(spec, dict), "spec 必须是 JSON 对象")

    for field in REQUIRED_TOP_FIELDS:
        _require(field in spec, f"spec 缺少必填字段：{field}")

    _require(_is_str(spec["software_name"]), "software_name 必须为非空字符串")
    _require(_is_str(spec["version"]), "version 必须为非空字符串（如 V1.0）")
    _require(_is_str(spec["subject"], max_len=20), "subject 必须为 1-20 字的业务主题词")
    _require(_is_str(spec["industry"]), "industry 必须为非空字符串")
    _require(_is_str(spec["target_users"]), "target_users 必须为非空字符串")

    _require(_is_str(spec["intro"], max_len=INTRO_MAX), f"intro 必须 ≤{INTRO_MAX} 字")
    _require(
        _is_str(spec["purpose"], max_len=PURPOSE_MAX),
        f"purpose 必须 ≤{PURPOSE_MAX} 字（当前长度 {len(spec.get('purpose', ''))}）",
    )
    mf_len = len(spec.get("main_features", "") or "")
    _require(
        isinstance(spec["main_features"], str) and MAIN_FEATURES_MIN <= mf_len <= MAIN_FEATURES_MAX,
        f"main_features 必须为 {MAIN_FEATURES_MIN}-{MAIN_FEATURES_MAX} 字（当前 {mf_len}）",
    )
    _require(_is_str(spec["technical_highlights"]), "technical_highlights 必须为非空字符串")
    _require(_is_str(spec["flow_text"]), "flow_text 必须为非空字符串")

    arch = spec["architecture"]
    _require(isinstance(arch, dict), "architecture 必须为对象")
    _require(_is_str(arch.get("description")), "architecture.description 必须为非空字符串")
    layers = arch.get("layers")
    _require(
        isinstance(layers, list) and ARCHITECTURE_LAYERS_MIN <= len(layers) <= ARCHITECTURE_LAYERS_MAX,
        f"architecture.layers 数量必须在 {ARCHITECTURE_LAYERS_MIN}-{ARCHITECTURE_LAYERS_MAX} 之间",
    )
    for idx, layer in enumerate(layers, start=1):
        _require(isinstance(layer, dict), f"architecture.layers[{idx}] 必须为对象")
        _require(_is_str(layer.get("name"), max_len=12), f"architecture.layers[{idx}].name 必须为 ≤12 字")
        comps = layer.get("components")
        _require(
            isinstance(comps, list) and 2 <= len(comps) <= 6 and all(_is_str(c, max_len=20) for c in comps),
            f"architecture.layers[{idx}].components 必须为 2-6 个 ≤20 字的字符串",
        )

    modules = spec["modules"]
    _require(
        isinstance(modules, list) and len(modules) == MODULE_COUNT,
        f"modules 数量必须为 {MODULE_COUNT}",
    )
    for idx, module in enumerate(modules, start=1):
        _require(isinstance(module, dict), f"modules[{idx}] 必须为对象")
        _require(_is_str(module.get("title"), max_len=20), f"modules[{idx}].title 必须为 ≤20 字")
        _require(_is_str(module.get("summary")), f"modules[{idx}].summary 必须为非空字符串")
        groups = module.get("groups")
        _require(
            isinstance(groups, list) and GROUPS_PER_MODULE_MIN <= len(groups) <= GROUPS_PER_MODULE_MAX,
            f"modules[{idx}].groups 必须为 {GROUPS_PER_MODULE_MIN}-{GROUPS_PER_MODULE_MAX} 个",
        )
        for g_idx, group in enumerate(groups, start=1):
            _require(isinstance(group, dict), f"modules[{idx}].groups[{g_idx}] 必须为对象")
            _require(
                _is_str(group.get("title"), max_len=24),
                f"modules[{idx}].groups[{g_idx}].title 必须为 ≤24 字",
            )
            steps = group.get("steps")
            _require(
                isinstance(steps, list) and STEPS_PER_GROUP_MIN <= len(steps) <= STEPS_PER_GROUP_MAX,
                f"modules[{idx}].groups[{g_idx}].steps 必须为 {STEPS_PER_GROUP_MIN}-{STEPS_PER_GROUP_MAX} 条",
            )
            for s_idx, step in enumerate(steps, start=1):
                _require(_is_str(step), f"modules[{idx}].groups[{g_idx}].steps[{s_idx}] 必须为非空字符串")
        code = module.get("code_snippets")
        _require(
            isinstance(code, list) and len(code) >= 1 and all(_is_str(s) for s in code),
            f"modules[{idx}].code_snippets 必须为至少 1 段代码字符串",
        )

    defaults = spec["defaults"]
    _require(isinstance(defaults, dict), "defaults 必须为对象")
    for field in REQUIRED_DEFAULTS:
        _require(_is_str(defaults.get(field)), f"defaults.{field} 必须为非空字符串")

    _require(_is_str(spec["development_date"]), "development_date 必须为非空字符串")
    _require(_is_str(spec["package_name"]), "package_name 必须为非空字符串")
    _require(_is_str(spec["class_prefix"]), "class_prefix 必须为非空字符串")


def normalize_spec(spec: dict) -> dict:
    """Fill derived fields and stable defaults."""
    spec = dict(spec)
    spec["safe_software_name"] = safe_filename(spec["software_name"])
    if "development_date" not in spec or not spec.get("development_date"):
        spec["development_date"] = date.today().strftime("%Y年%m月%d日")
    # Stamp module indices so the rest of the pipeline can rely on them.
    for idx, module in enumerate(spec["modules"], start=1):
        module["index"] = idx
    spec["image_plan"] = build_image_plan(spec)
    return spec


def build_image_plan(spec: dict) -> list[dict]:
    """Derive the 16-image plan from module titles. Image1 is always architecture."""
    modules = spec["modules"]
    scenes_per_module = [
        ["overview-home", "overview-focus"],
        ["record-edit", "record-success"],
        ["search-input", "search-result", "search-filter"],
        ["community-post", "community-detail", "community-reply"],
        ["dashboard-overview", "dashboard-dimensions"],
        ["manage-create", "manage-edit", "manage-archive"],
    ]
    plan = [{"filename": "image1.png", "scene": "architecture", "label": "系统架构图"}]
    image_index = 2
    for module, scenes in zip(modules, scenes_per_module):
        for s_idx, scene in enumerate(scenes):
            plan.append({
                "filename": f"image{image_index}.jpeg",
                "scene": scene,
                "label": module["title"] if s_idx == 0 else f"{module['title']}{['详情','结果','筛选','回复','维度','编辑','归档','提交'][min(s_idx - 1, 7)]}",
            })
            image_index += 1
    return plan


def _toc_line(title: str, page: int, indent: int = 0) -> str:
    prefix = "    " * indent
    dot_count = max(3, 48 - len(prefix) - len(title) - len(str(page)))
    return f"{prefix}{title} {'.' * dot_count} {page}"


def build_manual_sequence(spec: dict) -> list[str]:
    modules = spec["modules"]
    module_pages = [5, 7, 9, 12, 15, 17]
    texts = [
        "操作手册",
        f"基于Java&Vue的{spec['software_name']} {spec['version']}",
        "目录",
        _toc_line("一、软件简介", 3),
        _toc_line("二、业务流程与使用说明", 4),
        _toc_line("2.1 系统架构与整体业务流程", 4, indent=1),
        _toc_line("2.2 功能模块说明", 5, indent=1),
    ]
    for module, page in zip(modules, module_pages):
        texts.append(_toc_line(f"2.2.{module['index']} {module['title']}", page, indent=2))
    texts.extend([
        "一、软件简介",
        spec["intro"],
        "二、业务流程与使用说明",
        "2.1 系统架构与整体业务流程",
        spec["architecture"]["description"],
        spec["flow_text"],
        "2.2 功能模块说明",
    ])
    for module in modules:
        texts.append(f"2.2.{module['index']} {module['title']}")
        texts.append(module["summary"])
        texts.append("操作步骤：")
        for g_idx, group in enumerate(module["groups"], start=1):
            texts.append(f"2.2.{module['index']}.{g_idx} {group['title']}")
            for s_idx, step in enumerate(group["steps"], start=1):
                texts.append(f"（{s_idx}）{step}")
    return texts


def _split_snippet_lines(snippet: str) -> list[str]:
    """Normalize line endings, drop trailing blank lines, return list of lines."""
    lines = snippet.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def build_code_lines(spec: dict, min_non_empty_lines: int = 3200) -> list[str]:
    pkg = spec["package_name"]
    prefix = spec["class_prefix"]
    lines: list[str] = [
        f"package {pkg};",
        "",
        "import org.springframework.boot.SpringApplication;",
        "import org.springframework.boot.autoconfigure.SpringBootApplication;",
        "",
        "@SpringBootApplication",
        f"public class {prefix}Application {{",
        "    public static void main(String[] args) {",
        f"        SpringApplication.run({prefix}Application.class, args);",
        "    }",
        "}",
        "",
    ]

    for module in spec["modules"]:
        lines.append(f"// ===== Module: {module['title']} =====")
        lines.append("")
        for snippet in module["code_snippets"]:
            lines.extend(_split_snippet_lines(snippet))
            lines.append("")

    support_index = 1
    while sum(1 for line in lines if line.strip()) < min_non_empty_lines:
        lines.extend([
            f"package {pkg}.support;",
            "",
            "import java.util.ArrayList;",
            "import java.util.List;",
            "",
            f"public class {prefix}Support{support_index:03d} {{",
            "    private final List<String> logs = new ArrayList<>();",
            "    public void append(String message) { logs.add(message); }",
            "    public List<String> snapshot() { return new ArrayList<>(logs); }",
            "    public boolean contains(String keyword) {",
            "        return logs.stream().anyMatch(item -> item.contains(keyword));",
            "    }",
            "    public String exportText() { return String.join(\"\\n\", logs); }",
            "}",
            "",
        ])
        support_index += 1
    return lines


def load_spec(path: Path) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_spec(spec)
    return normalize_spec(spec)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and normalize a soft copyright spec.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    spec = load_spec(Path(args.spec))
    content = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
