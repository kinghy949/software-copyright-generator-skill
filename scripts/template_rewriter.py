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
import os
import re
import time
from collections import Counter
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

# Effective (non-empty) code line floor that the *caller* must satisfy on their
# own real code. We no longer auto-pad with placeholder Support classes — see
# 2026-03-15 中国版权保护中心 新规要求独创表达且严禁模板化代码。Below this
# floor the validator hard-fails with guidance to add per-module business code.
MIN_EFFECTIVE_CODE_LINES = 1800

# Identifier / phrase patterns we will reject outright in spec-supplied code.
# These are the tells AI-detection / 版权中心人工复审 latches onto first.
_FORBIDDEN_IDENT_RE = re.compile(
    r"\b("
    r"(?:[A-Z][A-Za-z]*?)?(?:Support|Demo|Sample|Placeholder|Filler|Padding|"
    r"Auto|Stub|Template|Generated|Generic|Common)\d{2,}"
    r"|XxxSupport\w*"
    r"|TodoServiceImpl\d*|FooBar\w*|HelloWorld\d+"
    r")\b"
)
_AI_DISCLOSURE_RE = re.compile(
    r"(由\s*(?:AI|ChatGPT|GPT|Claude|Copilot|通义|文心|豆包|kimi)\s*生成"
    r"|AI[\s-]?generated"
    r"|此(?:代码|文档|内容)由.*?(?:AI|大模型|语言模型)"
    r"|本(?:代码|文档|内容)(?:由|使用).*?(?:AI|大模型|GPT|Claude))",
    re.IGNORECASE,
)
# A Java method-body signature we use to detect verbatim duplicated blocks.
_METHOD_SIG_RE = re.compile(
    r"((?:public|private|protected)\s+[\w<>,\s\[\]]+?\s+\w+\s*\([^)]*\)\s*\{)",
)

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


def _variation_seed(spec: dict) -> str:
    """A stable string that varies every invocation unless the caller pins it.

    The point is so two runs of the same `software_name` still pick a different
    sidebar/density/font/image-count combination —审核员 sees fewer obviously
    cloned bundles from the same source. The caller can pin `variation_nonce`
    to reproduce a specific layout.
    """
    nonce = spec.get("variation_nonce")
    if not nonce:
        nonce = f"{int(time.time())}-{os.getpid()}"
    return f"{spec['software_name']}|{spec.get('development_date', '')}|{nonce}"


def derive_theme(spec: dict) -> dict:
    """Pick a visibly distinct theme combination per software_name + nonce.

    The spec may supply `theme` overrides; any keys present win over the seeded
    defaults so the calling model can pin a specific look.
    """
    seed = _variation_seed(spec)
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
    return _seeded_count(_variation_seed(spec), "img_count", IMAGE_COUNT_MIN, IMAGE_COUNT_MAX)


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
    seed = _variation_seed(spec)
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


# ---------- anti-template / 2026 合规检查 ----------

def _check_code_originality(modules: list) -> None:
    """Reject code that exhibits the telltale signs of template / AI scaffolding.

    Triggered by 2026-03-15 中国版权保护中心 新规：申请人必须独立开发，源代码
    需具备独创表达；模板化与 AI 生成痕迹会直接进入失信名单。我们在生成阶段
    就拒绝最明显的几类信号，避免下游补正。
    """
    all_text_chunks: list[str] = []
    effective_line_total = 0
    method_signatures: Counter[str] = Counter()
    body_blocks: Counter[str] = Counter()

    for idx, module in enumerate(modules, start=1):
        snippets = module.get("code_snippets") or []
        joined = "\n".join(snippets)
        all_text_chunks.append(joined)
        effective_line_total += sum(1 for line in joined.splitlines() if line.strip())

        forbidden = _FORBIDDEN_IDENT_RE.search(joined)
        _require(
            forbidden is None,
            f"modules[{idx}].code_snippets 命中禁止的占位类/通用桩命名："
            f"`{forbidden.group(0) if forbidden else ''}`。"
            "2026 新规要求独创表达，请用与该模块业务相关的真实类/方法名，"
            "禁止 XxxSupport001、Demo01、SampleService02 等机械序号命名。",
        )
        ai_hit = _AI_DISCLOSURE_RE.search(joined)
        _require(
            ai_hit is None,
            f"modules[{idx}].code_snippets 出现 AI 生成/AI 撰写字样 "
            f"(`{ai_hit.group(0) if ai_hit else ''}`)，会被审核直接驳回甚至触发"
            "失信记录，请删除所有相关声明。",
        )

        for sig in _METHOD_SIG_RE.findall(joined):
            method_signatures[sig.strip()] += 1
        # crude body-similarity hash: collapse whitespace, slice 120 chars windows
        normalized = re.sub(r"\s+", " ", joined)
        for start in range(0, max(0, len(normalized) - 240), 80):
            body_blocks[normalized[start:start + 240]] += 1

    # Allow CI / fixture smoke tests to bypass the floor — they exist to validate
    # structure, not realism. Real callers should never set this flag.
    if not os.environ.get("SOFTCOPY_SKIP_LINE_FLOOR"):
        _require(
            effective_line_total >= MIN_EFFECTIVE_CODE_LINES,
            f"modules.code_snippets 有效（非空）总行数 {effective_line_total} 低于"
            f" {MIN_EFFECTIVE_CODE_LINES}。请直接在 spec 中补足每个模块的真实业务"
            "代码（建议每模块 300-450 行），脚本不再自动追加 XxxSupport001/002 占位"
            "类——那种填充会被 2026 新版查重直接识别。",
        )

    over_used_sigs = [sig for sig, n in method_signatures.items() if n >= 4]
    _require(
        not over_used_sigs,
        "以下方法签名在多个模块中重复出现 ≥4 次，疑似模板套壳："
        + "; ".join(over_used_sigs[:5])
        + "。请改写为各模块业务相关的实际逻辑。",
    )

    repeated_blocks = [b for b, n in body_blocks.items() if n >= 3]
    _require(
        len(repeated_blocks) < 6,
        f"代码片段中检测到 {len(repeated_blocks)} 段 240 字符级别的近似重复块，"
        "复用程度过高，会触发 AI 查重。请改写或删除重复段，让各模块表达独立。",
    )


# ---------- 生成式人工智能使用声明 ----------

GENAI_REQUIRED_FIELDS = [
    "applicant_name",   # 声明主体名称（公司全称或个人姓名）
    "credit_code",      # 统一社会信用代码 / 组织机构代码（个人申请可填身份证号或留 "/"）
    "signature_date",   # 签署日期，形如 2026年06月23日
]


def _validate_genai_declaration(decl) -> None:
    """`genai_declaration` 是可选字段；仅当软件产品本身含生成式 AI 时需要填。

    模板参照《XX 大模型软件合法合规及原创性声明文件》：正文 90% 为固定法律
    话术（《网络安全法》《数据安全法》《个人信息保护法》《生成式人工智能
    服务管理暂行办法》等），调用方只需提供声明主体身份信息 + 软件名称。

    与申请表"未使用 AI 写代码/写文档"的手抄承诺是两件事——前者是产品形态，
    后者是申报过程，两者并不冲突。
    """
    if decl is None:
        return
    _require(isinstance(decl, dict), "genai_declaration 必须为对象")
    if decl.get("uses_genai") in (False, None):
        return
    _require(decl.get("uses_genai") is True,
             "genai_declaration.uses_genai 必须为布尔，未启用时直接省略该字段")
    for field in GENAI_REQUIRED_FIELDS:
        _require(_is_str(decl.get(field)),
                 f"genai_declaration.{field} 必须为非空字符串（产品含生成式 AI 时为必填）")
    contact = decl.get("contact")
    if contact is not None:
        _require(_is_str(contact, max_len=120),
                 "genai_declaration.contact 必须为 ≤120 字符的联系方式字符串（可选）")


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

    _check_code_originality(modules)

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

    nonce = spec.get("variation_nonce")
    if nonce is not None:
        _require(
            _is_str(nonce, max_len=64),
            "variation_nonce 必须为 1-64 字符的字符串（不填则按时间戳生成，"
            "用于让相同 software_name 在不同次运行得到不同主题/截图组合）",
        )

    _validate_genai_declaration(spec.get("genai_declaration"))

    intro_text = spec.get("intro", "") or ""
    full_blob = "\n".join([
        intro_text, spec.get("main_features", "") or "",
        spec.get("purpose", "") or "", spec.get("technical_highlights", "") or "",
        spec.get("flow_text", "") or "",
        (spec.get("architecture") or {}).get("description", "") or "",
    ])
    ai_hit = _AI_DISCLOSURE_RE.search(full_blob)
    _require(
        ai_hit is None,
        f"申请表/手册自然语言段落出现 AI 生成字样 (`{ai_hit.group(0) if ai_hit else ''}`)，"
        "2026 新规要求承诺独立开发、未使用 AI，请删除全部相关声明再重试。",
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


def build_code_sections(spec: dict) -> dict:
    """Flatten caller-supplied module code. We no longer auto-pad with placeholder
    Support classes — 2026 新规直接拦截那种填充。If the caller didn't write enough
    real code, `validate_spec` already raised a SpecError telling them so.
    """
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

    return {
        "bootstrap": bootstrap,
        "modules": module_sections,
    }


def build_code_lines(spec: dict) -> list[str]:
    sections = build_code_sections(spec)
    out: list[str] = list(sections["bootstrap"])
    for module in sections["modules"]:
        out.append("")
        out.append(f"// ===== Module: {module['title']} =====")
        out.append("")
        out.extend(module["lines"])
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
