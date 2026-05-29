---
name: software-copyright-generator
description: "Generate a software copyright registration material bundle for common Web systems. Use when the user asks for 软著, 软件著作权, 申请表, 操作手册, 代码文档, 三件套, or wants to generate copyright application materials from only a software name and a short Chinese system introduction. The skill expects the calling model (Claude / Codex) to write all natural-language content and Java/Vue code into a spec.json; the bundled Python pipeline validates the spec, renders 16 mockup images, builds three R Markdown files and compiles them to PDFs via xelatex (TinyTeX) with proper TOC, page numbers, fonts, and formatting."
---

# Software Copyright Generator

## Mission

You (the calling model) are the content author. The Python pipeline is a strict formatter.

Workflow for every invocation:

1. Read `系统全名` and `系统简介` from the user.
2. **Write all申请表 / 操作手册 / 代码文档 content yourself** into a fresh `spec.json` that conforms to the schema below. Do not reuse content from previous runs verbatim — vary the wording, module names that are appropriate to the system, code identifiers, and architecture layers each time. Two invocations with the same inputs should produce visibly different content.
3. Run `scripts/render_pdf.py --spec spec.json --output-dir <out>`. The script will:
   - validate the spec (and exit with a clear error if anything is wrong) before invoking R
   - render 16 mockup images by rendering Jinja HTML templates (under `templates/html/`) and screenshotting them via headless Chromium (Playwright); all 16 images share one palette derived from `software_name`
   - build three R Markdown files (`application.Rmd`, `manual.Rmd`, `code.Rmd`) under `<out>/_build/`
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
| `package_name` | string | non-empty | Java 包名，会用于占位 Support 类 |
| `class_prefix` | string | non-empty | Java 类前缀 |

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
  "code_snippets": ["≥1 段，建议 4–6 段的代码字符串"]
}
```

模块标题应当贴合系统业务，例如校园志愿系统的模块标题可以是「志愿活动总览」「活动信息录入」「志愿者智能检索」等，不要写成纯通用名词。

#### code_snippets 内容指导

- 单段是一份完整可读的代码（Java 类 / Vue 单文件组件 / SQL 建表脚本），保留 package 声明、import、注释。
- **目标量级：每个模块约 300 行真实代码（6 模块约 1800 行）**。脚本会自动追加占位 Support 类把总量补到 3200 行下限。
- Java 段使用 `package_name` 下的子包，类名以 `class_prefix` 开头或与模块业务相关，避免 6 个模块全用同一个类名。
- 不要在代码里出现与软件主题无关的残留关键字（例如其它项目名）。
- 代码里允许出现 Markdown 风格的 `// ----` 分隔注释，但不要使用三重反引号。

### `defaults`

13 个必填字段，全部为字符串：

`rights_acquisition`, `rights_scope`, `software_type`, `software_nature`,
`development_mode`, `publication_status`, `dev_hardware`, `run_hardware`,
`dev_os`, `dev_tools`, `run_platform`, `support_software`, `languages`

这些值通常稳定（原始取得 / 全部权利 / 应用软件 / 原创 / 单独开发 / 未发表 / 标准开发机硬件 / Windows / IDEA + Maven + Git / Java + Vue + MySQL 等），但每次仍由你写入，允许根据系统类型微调（例如桌面端可以把 `dev_tools` 改为 `Visual Studio` 等）。

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
- 代码总非空行 < 3200 时，脚本在「附录 A 通用工具类」自动追加占位 `XxxSupport001/002/…`

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

- `基于SpringBoot的<系统名>_申请表.pdf`
- `基于Java&Vue的<系统名>_操作手册.pdf`
- `基于Java&Vue的<系统名>_代码文档.pdf`
- `<系统名>_spec.json` (the normalized, validated spec)
- `mockups/` with 16 generated images
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
