#!/usr/bin/env python3
"""
Spec validation + structural assembly.

Content is provided by the invoking LLM via a spec.json that conforms to the
schema documented in SKILL.md. This module:

  - validate_spec(spec): raise SpecError with a clear message if any field
    violates length / cardinality constraints.
  - normalize_spec(spec): derive theme tokens, sidebar nav, and image plan so
    every run looks visibly different even with similar inputs.
  - build_code_sections(spec): flatten module code snippets and pad with
    placeholder support classes until the minimum line count is reached.

No hardcoded business content lives here. If a field is missing the script
errors out and the caller (LLM) is expected to retry.
"""
from __future__ import annotations

import argparse
import hashlib
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
IMAGE_COUNT_MIN = 8
IMAGE_COUNT_MAX = 16
NAV_ITEM_MAX = 10

# Pool of scene keys the model may pick from for any non-architecture image.
SUPPORTED_SCENES = [
    "dashboard-overview", "dashboard-dimensions",
    "overview-home", "overview-focus",
    "record-edit", "record-success",
    "search-input", "search-result", "search-filter",
    "community-post", "community-detail", "community-reply",
    "manage-create", "manage-edit", "manage-archive",
]


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


# ---------- hashing helpers ----------

def _hash_int(seed: str, salt: str = "") -> int:
    digest = hashlib.sha1(f"{salt}|{seed}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _pick(seed: str, salt: str, choices: list):
    return choices[_hash_int(seed, salt) % len(choices)]


def _seeded_count(seed: str, salt: str, min_v: int, max_v: int) -> int:
    return min_v + (_hash_int(seed, salt) % (max_v - min_v + 1))


# ---------- theme derivation ----------

SIDEBAR_STYLES = ["dark-gradient", "dark-flat", "light-rail", "accent-bar"]
DENSITIES = ["compact", "comfortable", "spacious"]
RADIUS_CHOICES = [4, 6, 8, 12]
FONT_FAMILIES = [
    '"PingFang SC", "Microsoft YaHei", "Hiragino Sans GB", system-ui, sans-serif',
    '"Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", sans-serif',
    '"Source Han Sans SC", "Noto Sans CJK SC", "PingFang SC", sans-serif',
    '"Hiragino Sans GB", "PingFang SC", "Microsoft YaHei", sans-serif',
]
SIDEBAR_WIDTHS = [180, 200, 220, 240]
TOPBAR_VARIANTS = ["crumbs-search-user", "search-user", "crumbs-user", "rich-tabs"]
KPI_LAYOUTS = ["cols-4", "cols-3-plus-1", "cols-2"]
CARD_BORDER_STYLES = ["soft", "thin", "shadow", "flat"]


def derive_theme(spec: dict) -> dict:
    """Pick a visibly distinct theme combination per software_name.

    The spec may supply `theme` overrides; any keys present win over the seeded
    defaults so the calling model can pin a specific look.
    """
    seed = spec["software_name"]
    theme = {
        "sidebar_style":   _pick(seed, "sidebar", SIDEBAR_STYLES),
        "density":         _pick(seed, "density", DENSITIES),
        "radius":          _pick(seed, "radius", RADIUS_CHOICES),
        "font_family":     _pick(seed, "font", FONT_FAMILIES),
        "sidebar_width":   _pick(seed, "sb_w", SIDEBAR_WIDTHS),
        "topbar":          _pick(seed, "topbar", TOPBAR_VARIANTS),
        "kpi_layout":      _pick(seed, "kpi", KPI_LAYOUTS),
        "card_border":     _pick(seed, "border", CARD_BORDER_STYLES),
    }
    overrides = spec.get("theme") if isinstance(spec.get("theme"), dict) else {}
    theme.update({k: v for k, v in overrides.items() if v})
    return theme


# ---------- nav derivation ----------

_DEFAULT_NAV_PREFIX = ["工作台"]
_DEFAULT_NAV_SUFFIX = ["系统设置"]


def derive_nav_items(spec: dict) -> list[str]:
    """Build a sidebar menu that mirrors the actual module list.

    Priority:
      1. spec["nav_items"] if supplied and non-empty.
      2. Otherwise: [工作台, <module 1 title>, ..., <module 6 title>, 系统设置]
         truncated to NAV_ITEM_MAX.

    Each item is also trimmed for display by the renderer; the raw label stays
    in the spec for the manual.
    """
    explicit = spec.get("nav_items")
    if isinstance(explicit, list) and explicit and all(_is_str(s, max_len=14) for s in explicit):
        return [s.strip() for s in explicit][:NAV_ITEM_MAX]

    seen = set()
    items: list[str] = []
    for label in (_DEFAULT_NAV_PREFIX
                  + [m["title"] for m in spec["modules"]]
                  + _DEFAULT_NAV_SUFFIX):
        if label and label not in seen:
            items.append(label)
            seen.add(label)
        if len(items) >= NAV_ITEM_MAX:
            break
    return items


# ---------- image plan ----------

SCENE_POOL_BY_KIND = {
    "dashboard": ["dashboard-overview", "dashboard-dimensions", "overview-home", "overview-focus"],
    "list":      ["overview-focus", "search-result", "manage-edit", "manage-archive"],
    "form":      ["record-edit", "manage-create"],
    "success":   ["record-success"],
    "search":    ["search-input", "search-filter", "search-result"],
    "community": ["community-post", "community-detail", "community-reply"],
}


def _module_scene_pool(module: dict, mod_idx: int) -> list[str]:
    """Resolve a per-module scene pool from explicit hints or the module index."""
    hints = module.get("scene_hints")
    pool: list[str] = []
    if isinstance(hints, list):
        for hint in hints:
            if hint in SUPPORTED_SCENES:
                pool.append(hint)
            elif hint in SCENE_POOL_BY_KIND:
                pool.extend(SCENE_POOL_BY_KIND[hint])
    if pool:
        return pool
    # Cycle through kinds by module index for a sensible default.
    cycle = [
        SCENE_POOL_BY_KIND["dashboard"],
        SCENE_POOL_BY_KIND["form"] + SCENE_POOL_BY_KIND["success"],
        SCENE_POOL_BY_KIND["search"],
        SCENE_POOL_BY_KIND["community"],
        SCENE_POOL_BY_KIND["dashboard"],
        SCENE_POOL_BY_KIND["list"] + SCENE_POOL_BY_KIND["form"],
    ]
    return cycle[(mod_idx - 1) % len(cycle)]


def _resolve_total_image_count(spec: dict) -> int:
    explicit = spec.get("image_plan_size")
    if isinstance(explicit, int) and IMAGE_COUNT_MIN <= explicit <= IMAGE_COUNT_MAX:
        return explicit
    return _seeded_count(spec["software_name"], "img_count", IMAGE_COUNT_MIN, IMAGE_COUNT_MAX)


def _distribute(total: int, buckets: int, seed: str) -> list[int]:
    """Distribute `total` items across `buckets`, at least 1 per bucket if possible.

    Deterministic from `seed`. Used to assign per-module screenshot counts.
    """
    if total <= buckets:
        # Some modules get 1, others get 0; rotate by hash.
        offsets = sorted(range(buckets), key=lambda i: _hash_int(seed, f"bucket-{i}"))
        out = [0] * buckets
        for i in offsets[:total]:
            out[i] = 1
        return out
    base = [1] * buckets
    remaining = total - buckets
    weights = [(_hash_int(seed, f"w-{i}") % 100) + 1 for i in range(buckets)]
    while remaining > 0:
        # Bucket with highest "deficit" (lowest current vs cap of 3) wins.
        best_idx = 0
        best_key = (-1, -1)
        for i in range(buckets):
            if base[i] >= 3:
                continue
            key = (3 - base[i], weights[i])
            if key > best_key:
                best_key = key
                best_idx = i
        if best_key == (-1, -1):
            break  # All capped; drop extras.
        base[best_idx] += 1
        remaining -= 1
    return base


def build_image_plan(spec: dict) -> list[dict]:
    """8-16 images: image1 is architecture; the rest distribute across modules.

    Each item carries `module_index` (1-based, or 0 for architecture) so the
    Rmd builder and the screenshot context can attribute the image correctly.
    """
    seed = spec["software_name"]
    total = _resolve_total_image_count(spec)
    per_module = _distribute(total - 1, MODULE_COUNT, seed)

    plan = [{
        "filename": "image1.png",
        "scene": "architecture",
        "label": "系统架构图",
        "module_index": 0,
    }]
    image_index = 2
    for mod_idx, (module, count) in enumerate(zip(spec["modules"], per_module), start=1):
        if count <= 0:
            continue
        pool = _module_scene_pool(module, mod_idx)
        figure_index = 0
        for j in range(count):
            scene = pool[(_hash_int(seed, f"scene-{mod_idx}-{j}")) % len(pool)]
            figure_index += 1
            label = module["title"] if figure_index == 1 else f"{module['title']}（场景{figure_index}）"
            plan.append({
                "filename": f"image{image_index}.jpeg",
                "scene": scene,
                "label": label,
                "module_index": mod_idx,
                "figure_index": figure_index,
            })
            image_index += 1
    return plan


# ---------- validation ----------

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
        hints = module.get("scene_hints")
        if hints is not None:
            _require(
                isinstance(hints, list) and all(
                    h in SUPPORTED_SCENES or h in SCENE_POOL_BY_KIND for h in hints
                ),
                f"modules[{idx}].scene_hints 必须为已知 scene/kind 列表",
            )

    defaults = spec["defaults"]
    _require(isinstance(defaults, dict), "defaults 必须为对象")
    for field in REQUIRED_DEFAULTS:
        _require(_is_str(defaults.get(field)), f"defaults.{field} 必须为非空字符串")

    _require(_is_str(spec["development_date"]), "development_date 必须为非空字符串")
    _require(_is_str(spec["package_name"]), "package_name 必须为非空字符串")
    _require(_is_str(spec["class_prefix"]), "class_prefix 必须为非空字符串")

    nav_items = spec.get("nav_items")
    if nav_items is not None:
        _require(
            isinstance(nav_items, list) and 3 <= len(nav_items) <= NAV_ITEM_MAX
            and all(_is_str(s, max_len=14) for s in nav_items),
            f"nav_items 必须为 3-{NAV_ITEM_MAX} 个 ≤14 字的字符串",
        )

    image_size = spec.get("image_plan_size")
    if image_size is not None:
        _require(
            isinstance(image_size, int) and IMAGE_COUNT_MIN <= image_size <= IMAGE_COUNT_MAX,
            f"image_plan_size 必须为 {IMAGE_COUNT_MIN}-{IMAGE_COUNT_MAX} 之间的整数",
        )


def _extract_code_package(snippets: list[str]) -> str | None:
    """Pull the first `package xxx;` declaration from a module's snippets."""
    for snippet in snippets:
        for line in snippet.splitlines():
            stripped = line.strip()
            if stripped.startswith("package ") and stripped.endswith(";"):
                return stripped[len("package "):-1].strip()
    return None


def normalize_spec(spec: dict) -> dict:
    """Fill derived fields and stable defaults."""
    spec = dict(spec)
    spec["safe_software_name"] = safe_filename(spec["software_name"])
    if "development_date" not in spec or not spec.get("development_date"):
        spec["development_date"] = date.today().strftime("%Y年%m月%d日")
    for idx, module in enumerate(spec["modules"], start=1):
        module["index"] = idx
        if not module.get("code_package"):
            pkg = _extract_code_package(module["code_snippets"])
            if pkg:
                module["code_package"] = pkg
    spec["theme"] = derive_theme(spec)
    spec["nav_items"] = derive_nav_items(spec)
    spec["image_plan"] = build_image_plan(spec)
    return spec


def _split_snippet_lines(snippet: str) -> list[str]:
    """Normalize line endings, drop trailing blank lines, return list of lines."""
    lines = snippet.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _bootstrap_lines(pkg: str, prefix: str) -> list[str]:
    return [
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
    ]


def _support_class_lines(pkg: str, prefix: str, index: int) -> list[str]:
    return [
        f"package {pkg}.support;",
        "",
        "import java.util.ArrayList;",
        "import java.util.List;",
        "",
        f"public class {prefix}Support{index:03d} {{",
        "    private final List<String> logs = new ArrayList<>();",
        "    public void append(String message) { logs.add(message); }",
        "    public List<String> snapshot() { return new ArrayList<>(logs); }",
        "    public boolean contains(String keyword) {",
        "        return logs.stream().anyMatch(item -> item.contains(keyword));",
        "    }",
        "    public String exportText() { return String.join(\"\\n\", logs); }",
        "}",
    ]


def _count_non_empty(*sections: list[str]) -> int:
    total = 0
    for section in sections:
        total += sum(1 for line in section if line.strip())
    return total


def build_code_sections(spec: dict, min_non_empty_lines: int = 3200) -> dict:
    pkg = spec["package_name"]
    prefix = spec["class_prefix"]

    bootstrap = _bootstrap_lines(pkg, prefix)

    module_sections: list[dict] = []
    for module in spec["modules"]:
        lines: list[str] = []
        for snippet_idx, snippet in enumerate(module["code_snippets"]):
            if snippet_idx > 0:
                lines.append("")
            lines.extend(_split_snippet_lines(snippet))
        module_sections.append({
            "title": module["title"],
            "lines": lines,
            "code_package": module.get("code_package"),
        })

    support: list[str] = []
    support_index = 1
    module_line_lists = [section["lines"] for section in module_sections]
    while _count_non_empty(bootstrap, *module_line_lists, support) < min_non_empty_lines:
        if support:
            support.append("")
        support.extend(_support_class_lines(pkg, prefix, support_index))
        support_index += 1

    return {
        "bootstrap": bootstrap,
        "modules": module_sections,
        "support": support,
    }


def build_code_lines(spec: dict, min_non_empty_lines: int = 3200) -> list[str]:
    sections = build_code_sections(spec, min_non_empty_lines)
    out: list[str] = list(sections["bootstrap"])
    for module in sections["modules"]:
        out.append("")
        out.append(f"// ===== Module: {module['title']} =====")
        out.append("")
        out.extend(module["lines"])
    if sections["support"]:
        out.append("")
        out.extend(sections["support"])
    return out


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
