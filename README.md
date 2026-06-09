# software-copyright-generator

[![CI](https://github.com/kinghy949/software-copyright-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/kinghy949/software-copyright-generator/actions/workflows/ci.yml)

一个软著三件套（申请表 / 操作手册 / 代码文档）的**PDF 结构化组装器**，配合 Claude Code / Codex 使用。

![Preview](./assets/showcase/preview-collage.jpg)

## 设计思路

**职责切分**：

- **内容**（每次不同）：所有中文文案、模块名、代码片段、架构图层名都由调用方的大模型现写，写进一份 `spec.json`
- **格式**（每次相同）：Python + R Markdown + xelatex 把 spec 编译成 PDF：真正的 PDF 目录、自动章节编号、统一字体、自动分页、自动图题编号

两次同样的「系统全名 + 系统简介」会生成内容不同、但排版完全一致的三份 PDF。

不同软件名会自动派生**不同的视觉主题**（侧边栏样式 / 内边距 / 圆角 / 字体 / 顶栏布局 / 卡片边框）和**不同的菜单结构**（默认用 6 个模块标题作为侧边栏项），让多份软著看起来不像一套模板。

## 快速开始

```bash
git clone git@github.com:kinghy949/software-copyright-generator.git
cd software-copyright-generator

# Python 依赖
pip install -r requirements.txt

# R + TinyTeX 依赖（一次性安装）
Rscript -e 'install.packages(c("rmarkdown","knitr","tinytex"), repos="https://cloud.r-project.org")'
Rscript -e 'tinytex::install_tinytex(force = TRUE)'

# Linux 还需要：sudo apt install -y pandoc fonts-noto-cjk
# macOS / Windows 系统自带宋体或 PingFang
```

让模型按 `SKILL.md` 的 schema 写 `spec.json`（参考 `assets/fixtures/sample_spec.json`），再执行：

```bash
python scripts/render_pdf.py \
  --spec ./spec.json \
  --output-dir ./output
```

生成：

- `<系统名>_申请表.pdf` — 封面 + 3 张属性表
- `<系统名>_操作手册.pdf` — 封面 + 真目录 + 系统架构图 + 6 模块章节（含到代码文档的交叉引用）+ 8–16 张配图
- `<系统名>_代码文档.pdf` — 封面 + 真目录 + 6 模块代码 + 附录 A 通用工具类
- `<系统名>_spec.json`（已校验、已补齐衍生字段，含主题 / 菜单 / 图片计划）
- `mockups/` 8–16 张配图（数量由 `image_plan_size` 或软件名哈希决定）
- `_build/` 中间 Rmd / tex 源码（调试用）

## 由 Rmd + LaTeX 兜底的格式规则

每次都生效，无需写进 spec：

- 全文 **宋体（CJK）+ Times New Roman（Latin）+ 五号 + 黑色**
- 操作手册 / 代码文档自带 **真正的 PDF TOC**（可点击跳转，页码自动更新）
- 章节编号 / 图题编号自动（`图 2-1`、`图 2-2-1` 等）
- 每个模块自动 `\clearpage` 开新页
- 三份 PDF 都有：封面页 + 含软件名/版本/文档类型的页眉 + 居中页码
- 申请表 `开发目的` ≤50 字、`主要功能` 500–1300 字 — Python 校验，错了直接报错让模型重写
- 代码总非空行 ≥ 3200：模型不够时脚本在「附录 A 通用工具类」自动补齐占位 `XxxSupport001/002/…`

## 由模型每次现写的内容

- `intro / purpose / main_features / technical_highlights / flow_text`
- `architecture.description / architecture.layers`
- 6 个 `modules` 的 `title / summary / groups / steps / code_snippets`
  - 可选 `scene_hints`：指定该模块截图采用哪类场景（dashboard/list/form/success/search/community 或具体 scene key）
- `package_name / class_prefix / development_date`
- `defaults`（建议沿用稳定值，但允许按系统类型微调）

## 由模型可选覆写的随机项

不写时由 `software_name` 哈希派生，每个系统天然不同；显式写入则按指定值生效。

- `nav_items` — 侧边栏菜单（3–10 项 ≤14 字），默认 = `[工作台] + 模块标题 + [系统设置]`
- `image_plan_size` — 截图总数（8–16，含 1 张架构图）
- `theme` — 视觉主题（任一键可单独覆写）：
  - `sidebar_style`：`dark-gradient | dark-flat | light-rail | accent-bar`
  - `density`：`compact | comfortable | spacious`
  - `radius`：`4 | 6 | 8 | 12`
  - `sidebar_width`：`180 | 200 | 220 | 240`
  - `font_family`：自定义 CSS 字体栈
  - `topbar`：`crumbs-search-user | search-user | crumbs-user | rich-tabs`
  - `card_border`：`soft | thin | shadow | flat`

## 操作手册 ↔ 源程序鉴别材料一致性

为满足软著审查中「文档鉴别材料与源程序鉴别材料相符」的要求：

- 每个模块的标题同时出现在**侧边栏菜单**、**操作手册章节**、**代码文档章节**三处。
- 操作手册每个模块下自动追加一行交叉引用：「本模块业务逻辑由 `com.x.y.z` 包下的核心类承载，完整源码详见《代码文档》中「<模块名>」一章」（`package` 行从 `code_snippets` 自动解析）。
- 截图按 `module_index` 归属到对应模块，截图中侧边栏的高亮项也指向该模块。

## 仓库定位

适合：

- 项目交付时快速生成「格式合规、内容贴合实际项目」的软著三件套 PDF 草稿
- 让大模型完成创意文案 + 代码片段，让脚本完成排版

不负责：

- 官方在线正式填报
- 权利人身份证明、营业执照、委托书等主体材料
- 法律真实性校验

## 目录结构

```text
software-copyright-generator/
├── SKILL.md                    # 内容生成 playbook（模型必读）
├── README.md
├── assets/
│   ├── fixtures/
│   │   └── sample_spec.json    # 参考 spec，CI 用作 stand-in
│   └── showcase/
│       └── preview-collage.jpg
├── templates/
│   └── rmd/
│       ├── preamble.tex        # 共享 LaTeX preamble（字体/listings/页眉/目录）
│       ├── cover.tex.j2        # 封面 Jinja 模板
│       ├── header.tex.j2       # 页眉 Jinja 模板
│       ├── application.Rmd.j2  # 申请表
│       ├── manual.Rmd.j2       # 操作手册
│       └── code.Rmd.j2         # 代码文档
├── references/
│   └── requirements.md
└── scripts/
    ├── render_pdf.py           # 入口：校验 → 配图 → Rmd → PDF
    ├── build_rmd.py            # Jinja 渲染三份 Rmd
    ├── render_mockups.py       # 8–16 张配图渲染（含架构图，主题驱动样式）
    ├── template_rewriter.py    # spec 校验 + 代码分段 + 行数兜底
    └── smoke_test.py           # CI 端到端冒烟测试
```

## 安装到 Codex / Claude Code

```bash
git clone git@github.com:kinghy949/software-copyright-generator.git \
  ~/.codex/skills/software-copyright-generator
```

## 依赖环境

- Python 3.12+ : `Jinja2`, `pikepdf`, `playwright`（首次还需 `playwright install chromium`）
- R 4.x : `rmarkdown`, `knitr`, `tinytex`
- TinyTeX (xelatex) — 首次渲染时自动拉取缺失的 LaTeX 包
- pandoc ≥ 2
- CJK 字体（Linux: `fonts-noto-cjk`；macOS/Windows 系统自带）

## 校验

```bash
python scripts/smoke_test.py
```

烟雾测试使用 `assets/fixtures/sample_spec.json` 作为模型产出的 stand-in，验证 schema 校验 + 三份 PDF 编译 + 目录书签数 + 代码 PDF 页数 ≥ 40 + 截图数量落在 8–16 区间。

## 说明

输出为软著材料 PDF 草稿，重点是格式合规和成稿率。正式提交前仍建议人工检查：

- 软件名称是否统一
- 主要功能是否与系统实际一致
- 技术特点是否符合真实项目
- 代码文档是否需要把占位 Support 类替换为真实源码片段
