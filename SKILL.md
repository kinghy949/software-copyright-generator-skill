---
name: software-copyright-generator
description: "Generate a software copyright registration material bundle for common Web systems. Use when the user asks for 软著, 软件著作权, 申请表, 操作手册, 代码文档, 三件套, or wants to generate copyright application materials from only a software name and a short Chinese system introduction. The skill expects the calling model (Claude / Codex) to write all natural-language content and Java/Vue code into a spec.json; the bundled Python pipeline validates the spec, renders 8-16 mockup images with a per-spec theme and sidebar derived from the actual modules, builds three R Markdown files and compiles them to PDFs via xelatex (TinyTeX) with proper TOC, page numbers, fonts, and formatting. The manual and code documents cross-reference each other so the source program 鉴别材料 matches the operation manual."
---

# Software Copyright Generator

## Mission

You (the calling model) are the content author. The Python pipeline is a strict formatter.

> ⚠️ **2026-03-15 起中国版权保护中心新规**：申请人须手抄承诺"软件确系独立开发，未使用 AI 开发编写代码、撰写文档或生成登记申请材料"，失实者列入版权登记失信名单 + 个人征信。同时启用了跨申请人 AI 查重，模板化代码 / 通用桩 / 套壳文档极易被驳回或要求补正。本 skill 已在 spec 验证阶段拦截最明显的几类信号，但**独创表达的根本责任在你（调用方模型）**。详见 [`references/requirements.md`](references/requirements.md)。

Workflow for every invocation:

1. Read `系统全名` 和 `系统简介` from the user.
2. **Write all申请表 / 操作手册 / 代码文档 content yourself** into a fresh `spec.json` that conforms to the schema below. 强制要求：
   - 每个模块的代码必须围绕该业务的真实领域名词命名（实体、状态机、流程节点），禁止 `Support001 / Demo01 / SampleService / TodoServiceImpl` 这类机械命名 —— 验证器会直接 reject。
   - 不在任何文档或代码注释里出现 "AI 生成 / ChatGPT / 大模型撰写" 之类字样。
   - 注释体现人类调试思路（业务约束、踩坑提示、TODO 引用真实接口名），不要逐行解释 `i++`。
   - 两次同名系统的运行必须可见差异：模块拆分角度、字段命名、表结构、算法实现都要换；可借助下面的 `variation_nonce` 让脚本同时换主题/截图组合。
   - **不复用历史申请人已登记的代码**（2026 新规会和历史申请库对比）。
3. Run `scripts/render_pdf.py --spec spec.json --output-dir <out>`. The script will:
   - validate the spec (and exit with a clear error if anything is wrong) before invoking R
   - derive a visual **theme** (sidebar style, density, corner radius, font, topbar variant, card-border style) and a **sidebar nav** (defaulting to module titles, so each system gets a unique menu) from the spec
   - render 8-16 mockup images by rendering Jinja HTML templates (under `templates/html/`) and screenshotting them via headless Chromium (Playwright); image count is deterministic-per-software_name (or set explicitly via `image_plan_size`), all images share one palette + theme so the bundle reads as one product
   - build three R Markdown files (`application.Rmd`, `manual.Rmd`, `code.Rmd`) under `<out>/_build/`; the manual cross-references each module's Java package so the 操作手册 and 代码文档 stay aligned
   - call `Rscript -e 'rmarkdown::render(...)'` per document to compile each into a PDF via xelatex
   - copy the PDFs to `<out>/` with friendly names
4. If the script errors, **read the error message and rewrite spec.json**; do not bypass the script.

You must not hardcode content from this file into the spec — these are constraints, not snippets to copy.

## spec.json Schema

Required top-level fields (the validator will reject the spec if any is missing or violates a constraint):

| Field | Type | Constraint | Notes |
| --- | --- | --- | --- |
| `software_name` | string | non-empty | full Chinese name as supplied by the user |
| `version` | string | non-empty | usually `V1.0` |
| `subject` | string | 1–20 字 | short business subject extracted from the name (e.g. `校园志愿`) |
| `industry` | string | non-empty | e.g. `教育信息化`, `医疗健康`, `物业管理` |
| `target_users` | string | non-empty | one phrase describing primary users |
| `intro` | string | ≤140 字 | one-paragraph system summary |
| `purpose` | string | **≤50 字** | 开发目的，超过会被验证器拒绝 |
| `main_features` | string | **500–1300 字** | 主要功能段落，必须落在区间内 |
| `technical_highlights` | string | non-empty | 1–2 句技术特点 |
| `flow_text` | string | non-empty | 整体业务流程描述 |
| `architecture` | object | see below | 架构图与文字描述 |
| `modules` | array | **恰好 6 个** | 功能模块 |
| `defaults` | object | see below | 申请表的固定字段值 |
| `development_date` | string | non-empty | 形如 `2026年05月29日` |
| `package_name` | string | non-empty | Java 包名（仅用于 SpringBoot 引导类的 `package` 声明，不再生成占位类） |
| `class_prefix` | string | non-empty | Java 类前缀；仅用于 `XxxApplication` 引导类，业务类请按领域取名 |
| `nav_items` | array | optional, 3-10 ≤14 字 | 侧边栏菜单（不写则用模块标题自动生成）；模型可写入符合系统业务的真实菜单 |
| `image_plan_size` | int | optional, 8-16 | 截图总数（含 1 张架构图）；不写则按 `software_name + variation_nonce` 哈希确定 |
| `variation_nonce` | string | optional, ≤64 字符 | 仅用于让重复运行获得不同主题/截图组合；不填时按当前时间戳生成，因此每次运行天然不同；若需复现某次结果，把上次 normalized spec 里的 `variation_nonce` 拷过来即可 |
| `theme` | object | optional | 视觉主题覆写，键见下文 |
| `genai_declaration` | object | optional | 仅当软件产品本身含生成式 AI（大模型对话、AIGC 文本/图像、智能审核 等）时填写；填了会额外产出第 4 份 PDF《生成式人工智能使用声明》；详见下文 |

### `architecture`

```jsonc
{
  "description": "string，架构说明段，写入操作手册 2.1 节",
  "subtitle": "string，可选，画在架构图标题下方（如 '前后端分离 · 分层架构 · Spring Boot + Vue + MySQL'）",
  "layers": [
    { "name": "≤12 字", "components": ["2–6 个 ≤20 字 字符串"] }
    // 4–6 层，建议顺序：用户层 → 前端层 → 接口层 → 业务/服务层 → 数据访问层 → 数据/基础设施
  ]
}
```

层名和组件名应当结合 `intro` 里的实际技术栈关键词（如 React/Vue/小程序/SpringBoot/Node/PostgreSQL/MongoDB）取真实存在的命名，而不是机械复用模板。

### `modules` （6 个）

每个模块对象：

```jsonc
{
  "title": "≤20 字",
  "summary": "本节简介段（写入操作手册）",
  "groups": [
    {
      "title": "≤24 字 小标题（写入 2.2.x.y）",
      "steps": ["2–5 条操作步骤，每条 1 句话"]
    }
    // 2–4 个 group
  ],
  "code_snippets": ["≥1 段，建议 4–6 段的代码字符串"],
  // optional — 影响该模块对应截图选用的场景；不写则按模块序号自动挑选
  "scene_hints": ["dashboard", "list", "form", "success", "search", "community",
                  // 或具体 scene key 如 "record-edit"]
}
```

`scene_hints` 接受两类值：
- **kind**：`dashboard` / `list` / `form` / `success` / `search` / `community`（每个 kind 自动展开为对应场景集合）
- **scene key**：完整列表见 `SUPPORTED_SCENES`，覆盖 `dashboard-overview` / `dashboard-dimensions` / `overview-home` / `overview-focus` / `record-edit` / `record-success` / `search-input` / `search-result` / `search-filter` / `community-post` / `community-detail` / `community-reply` / `manage-create` / `manage-edit` / `manage-archive`

模块标题既会出现在侧边栏（除非显式提供 `nav_items`），又会作为操作手册章节名 + 代码文档章节名，保证两份文档一一对应。

模块标题应当贴合系统业务，例如校园志愿系统的模块标题可以是「志愿活动总览」「活动信息录入」「志愿者智能检索」等，不要写成纯通用名词。

#### code_snippets 内容指导（2026 新规重点）

- 单段是一份完整可读的代码（Java 类 / Vue 单文件组件 / SQL 建表脚本），保留 package 声明、import、注释。
- **每个模块至少写 300–450 行真实业务代码，6 模块合计 ≥1800 有效行（验证器硬阈值）**。脚本不再自动追加 `XxxSupport001/002` 占位类——那种填充会被新版 AI 查重直接识别为模板套壳。
- Java 段使用 `package_name` 下贴近模块业务的子包（例如 `volunteer.activity`, `volunteer.search`），类名按领域取（`ActivityArchiver`、`MatchScoreRanker`），不要全篇 `XxxServiceImpl` 或 `Common*`。
- 同一方法签名跨模块出现 ≥4 次、240 字符的代码块跨模块重复 ≥3 次都会被验证器拒绝——必须让各模块的实现彼此不同。
- 注释要写"为什么"，引用真实业务约束（"活动结束 24h 后允许追加签到"），不要每行 `// 设置 id`。
- 任何位置都不能出现 "AI 生成 / 由 ChatGPT 撰写 / Claude 生成" 字样，否则申请表段落与代码都会被验证器拒绝。
- 代码里允许出现 Markdown 风格的 `// ----` 分隔注释，但不要使用三重反引号。

### `defaults`

13 个必填字段，全部为字符串：

`rights_acquisition`, `rights_scope`, `software_type`, `software_nature`,
`development_mode`, `publication_status`, `dev_hardware`, `run_hardware`,
`dev_os`, `dev_tools`, `run_platform`, `support_software`, `languages`

这些值通常稳定（原始取得 / 全部权利 / 应用软件 / 原创 / 单独开发 / 未发表 / 标准开发机硬件 / Windows / IDEA + Maven + Git / Java + Vue + MySQL 等），但每次仍由你写入，允许根据系统类型微调（例如桌面端可以把 `dev_tools` 改为 `Visual Studio` 等）。

### `genai_declaration` （仅产品本身含生成式 AI 时填）

> ⚠️ 注意区分两件事：
> 1. **申请表手抄承诺**——"未使用 AI 撰写代码/文档/材料"，是申报过程要求，无论填不填本字段都必须遵守，验证器也会自动拦截材料里出现 AI 字样。
> 2. **本字段**——描述的是软件产品里**对最终用户提供的生成式 AI 能力**（智能客服、AIGC 文案、智能审核、推荐生成等）。两件事互不冲突：产品里集成 LLM 是合法的，只要按本声明如实披露即可。

模板参照《XX 大模型软件合法合规及原创性声明文件》范式：正文 90% 是关于《网络安全法》《数据安全法》《个人信息保护法》《生成式人工智能服务管理暂行办法》的法律话术，调用方只需提供主体身份信息：

```jsonc
{
  "uses_genai": true,                          // false 或缺省时不会生成第 4 份 PDF
  "applicant_name": "北京示例科技有限公司",       // 公司全称；个人申请填本人姓名
  "credit_code": "91110108MA01XXXXXX",         // 统一社会信用代码 / 组织机构代码；个人填身份证号或 "/"
  "contact": "电话：010-12345678；邮箱：legal@example.com",  // 可选；填了会出现在第一节
  "signature_date": "2026年06月23日"
}
```

填了之后输出目录会多出 `<系统名>_合法合规及原创性声明文件.pdf`，五节结构：声明主体信息 → 软件作品声明（合法合规 + 原创性）→ 生成式人工智能服务声明（合法合规 + 服务规范）→ 生成内容声明（合法合规 + 原创性/权利归属）→ 其他声明 + 签章页。

**正式提交前请打印后由声明主体盖章或亲笔签字**（2026 新规要求黑色中性笔亲笔，禁止打印代签）。

### `theme` （可选覆写）

不写则由 `software_name` 哈希派生，所有键都可单独覆写：

```jsonc
{
  "sidebar_style": "dark-gradient | dark-flat | light-rail | accent-bar",
  "density":       "compact | comfortable | spacious",
  "radius":        4 | 6 | 8 | 12,
  "sidebar_width": 180 | 200 | 220 | 240,
  "font_family":   "<CSS font stack>",
  "topbar":        "crumbs-search-user | search-user | crumbs-user | rich-tabs",
  "kpi_layout":    "cols-4 | cols-3-plus-1 | cols-2",
  "card_border":   "soft | thin | shadow | flat"
}
```

通常不需要填——目的就是让不同软件名自动出来不同观感。仅当用户明确希望某种风格时再覆写。

## Format Constraints Enforced by the Pipeline

You do not need to set these — the LaTeX preamble (`templates/rmd/preamble.tex`) and the Rmd templates apply them on every render:

- 全文 **宋体** （CJK，fallback `Songti SC` → `Noto Serif CJK SC` → `PingFang SC`） + **Times New Roman** （Latin）+ **五号**（10.5pt）+ **黑色**
- 操作手册和代码文档自带 **真正的 PDF 目录**（pandoc 生成 `\tableofcontents`，可点击跳转、页码自动）
- 章节自动编号：申请表三大表区不编号；操作手册 `1 / 2.1 / 2.2.x` 自动；代码文档 `1 / 2 / …` 自动
- 模块小节内部用 Jinja 显式编号 `（1）/（2）/…` 标步骤
- 每个模块自动 `\clearpage` 开新页
- 操作手册架构图嵌入位置：2.1 节 `图 2-1 系统架构图`
- 模块截图嵌入：2.2.x 节内带 `图 2-x-y` 题注
- 三份 PDF 都有封面页（标题 + 副标题 + 版本 + 日期）+ 页眉（含软件名/版本/文档类型）+ 居中页码
- 代码文档使用 `listings` 框线 + 行号，全黑（无语法着色）
- 代码文档不再有「附录 A 通用工具类」；最终行数完全取决于你写入的 module code_snippets（验证器要求 ≥1800 有效行）

## Prerequisites (one-time)

The host machine must have:

- Python 3.12+ with `Jinja2`, `pikepdf`, `playwright` (see `requirements.txt`)
- Playwright Chromium browser: `playwright install chromium` (one-time, ~150 MB)
- R 4.x with packages `rmarkdown`, `knitr`, `tinytex`
- TinyTeX (`tinytex::install_tinytex()`) — provides `xelatex` and auto-installs missing LaTeX packages on first use
- pandoc ≥ 2 (system package, or shipped with RStudio)
- CJK fonts: macOS / Windows have 宋体 by default; Linux needs `fonts-noto-cjk`

## Workflow Example

```bash
# Author spec.json (this is your job — content varies every run)
$EDITOR spec.json

# Validate + render to PDF
python scripts/render_pdf.py --spec spec.json --output-dir ./out

# If validation fails:
#   - read the SpecError message printed to stderr
#   - fix the offending field in spec.json
#   - re-run
```

The render output directory contains:

- `<系统名>_申请表.pdf`
- `<系统名>_操作手册.pdf`
- `<系统名>_代码文档.pdf`
- `<系统名>_合法合规及原创性声明文件.pdf`（仅当 spec 里 `genai_declaration.uses_genai=true` 时产出）
- `<系统名>_spec.json` (the normalized, validated spec — includes resolved `theme`, `nav_items`, `image_plan`)
- `mockups/` with 8-16 generated images (number depends on `image_plan_size` / hash)
- `_build/` with the intermediate Rmd / tex sources (useful for debugging LaTeX errors)

## What This Skill Will Not Do

- Generate content from a Python template (the previous version did; it no longer does).
- Reuse a hardcoded module list. You must invent modules that suit the system.
- Emit `.docx` (the previous version did; PDF only now).
- Provide an `--offline` mode. The pipeline always requires a spec produced by you.
- Submit anything to an official copyright registration system.

## Files

- `scripts/render_pdf.py` — entry point; validate spec → render mockups → build Rmd → compile PDFs.
- `scripts/build_rmd.py` — Jinja2-renders the three Rmd files (+ shared `.tex` includes) under `<out>/_build/`.
- `scripts/template_rewriter.py` — spec schema, validator, code-section builder (including 3200-line floor padding).
- `scripts/render_mockups.py` — 16-image renderer: derives one palette from `software_name`, picks a Jinja HTML template per scene (`templates/html/*.html.j2`), and screenshots each via Playwright Chromium. The rendered HTML for each image is preserved under `<out>/mockups/_html/` for debugging.
- `templates/html/` — `base.html.j2` (shared layout with sidebar/topbar/palette variables) + per-scene templates (`architecture`, `dashboard`, `list`, `form`, `success`, `search`, `community`). Scene→template mapping lives in `render_mockups.SCENE_TEMPLATE`.
- `scripts/smoke_test.py` — CI smoke test; uses `assets/fixtures/sample_spec.json` as a stand-in.
- `templates/rmd/preamble.tex` — shared LaTeX preamble: fonts, listings, fancyhdr, hyperref, geometry, captions.
- `templates/rmd/cover.tex.j2` / `header.tex.j2` — per-document Jinja includes for title page and page header.
- `templates/rmd/{application,manual,code}.Rmd.j2` — Rmd Jinja templates.
- `assets/fixtures/sample_spec.json` — a reference spec showing every field filled. Use as a structural example only.
- `references/requirements.md` — formal 软著 review notes (read only when the user asks about compliance / 审查风险).

## Practical Notes

- Treat this skill as a fast structural assembler. The realism of the output depends entirely on the quality of the spec you write.
- After running, open the three `.docx` files to spot-check the rendered output before reporting success.
- If the user revises the system name or features mid-conversation, rewrite the full spec and re-render; do not edit the docx directly.
