# software-copyright-generator

[![CI](https://github.com/kinghy949/software-copyright-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/kinghy949/software-copyright-generator/actions/workflows/ci.yml)

一个软著三件套（申请表 / 操作手册 / 代码文档）的**结构化组装器**，配合 Claude Code / Codex 使用。

![Preview](./assets/showcase/preview-collage.jpg)

## 设计思路

这是一个**职责切分**的 skill：

- **内容**（每次不同）：所有中文文案、模块名、代码片段、架构图层名都由调用方的大模型现写，写进一份 `spec.json`
- **格式**（每次相同）：Python 脚本只做 schema 校验、docx 组装、字体/颜色/编号统一、配图嵌入、代码行数兜底

所以两次同样的「系统全名 + 系统简介」会生成内容完全不同、但格式完全一致的三件套。

> 想了解为什么这样设计、和「纯模板生成」的差别，看 `SKILL.md` 顶部。

## 快速开始

```bash
git clone git@github.com:kinghy949/software-copyright-generator.git
cd software-copyright-generator
pip install -r requirements.txt
```

把 skill 安装到 Codex / Claude Code 后，让模型按 `SKILL.md` 的 schema 写出 `spec.json`，再执行：

```bash
python scripts/render_bundle.py \
  --spec ./spec.json \
  --output-dir ./output
```

生成：

- `基于SpringBoot的<系统名>_申请表.docx`
- `基于Java&Vue的<系统名>_操作手册.docx`
- `基于Java&Vue的<系统名>_代码文档.docx`
- `<系统名>_spec.json`（已校验、已补齐衍生字段的副本）
- `mockups/` 16 张配图

如果想看完整的 spec 长什么样，参考 `assets/fixtures/sample_spec.json`。

## 由脚本兜底的格式规则

下列规则不依赖模型，每次都生效：

- 申请表 `开发目的` ≤50 字、`主要功能` 500–1300 字 —— 校验不过会报错让模型重写
- 操作手册 6 模块 = `modules` 数组长度 = 6 —— 校验
- 申请表 / 操作手册 全文 **宋体 五号 黑色**
- 代码文档 **Times New Roman + 宋体（中文） 五号 黑色**
- 操作手册目录：缩进 + 点引线 + 页码
- 小节编号：`2.2.x` → `2.2.x.y` → `（n）`
- 代码文档总非空行 ≥ 3200 行：模型现写的真实代码不足时，脚本追加占位 `XxxSupport001/002/…` 类补齐
- 操作手册 2.1 节自动嵌入「系统架构图」，层名 / 组件名来自 `spec.architecture.layers`

## 由模型每次现写的内容

- `intro / purpose / main_features / technical_highlights / flow_text`
- `architecture.description / architecture.layers`
- 6 个 `modules` 的 `title / summary / groups / steps / code_snippets`
- `package_name / class_prefix / development_date`
- `defaults`（建议沿用稳定值，但允许按系统类型微调）

## 仓库定位

适合：

- 项目交付时快速生成「格式合规、内容贴合实际项目」的软著三件套草稿
- 让大模型完成创意文案 + 代码片段，让脚本完成排版

不负责：

- 官方在线正式填报
- 权利人身份证明、营业执照、委托书等主体材料
- 法律真实性校验

## 目录结构

```text
software-copyright-generator/
├── SKILL.md               # 内容生成 playbook（模型必读）
├── README.md
├── assets/
│   ├── fixtures/
│   │   └── sample_spec.json   # 参考 spec，CI 用作 stand-in
│   ├── showcase/
│   │   └── preview-collage.jpg
│   └── templates/
│       ├── template_application.docx
│       ├── template_manual.docx
│       └── template_code.docx
├── references/
│   └── requirements.md
└── scripts/
    ├── render_bundle.py
    ├── render_mockups.py
    ├── template_rewriter.py
    └── smoke_test.py
```

## 安装方式

放到 Codex / Claude Code 的 skills 目录下：

```bash
git clone git@github.com:kinghy949/software-copyright-generator.git \
  ~/.codex/skills/software-copyright-generator
```

或独立调用脚本，克隆到任意目录后运行 `scripts/render_bundle.py`。

## 依赖环境

- Python 3.12+
- `python-docx`
- `Pillow`

脚本会自动按顺序探测 Windows / macOS / Linux 的中文字体（雅黑、宋体、PingFang、Noto CJK、文泉驿），无需手动配置。

```bash
pip install -r requirements.txt
```

## 校验

```bash
python scripts/smoke_test.py
```

烟雾测试使用 `assets/fixtures/sample_spec.json` 作为模型产出的 stand-in，验证 schema 校验 + 三个 docx 组装 + 配图嵌入 + 代码行数兜底是否全部通过。

## 说明

这个项目输出的是「软著材料草稿」，重点是格式合规和成稿率，不等同于官方申报系统，也不保证直接通过审查。正式提交前仍建议人工检查：

- 软件名称是否统一
- 主要功能是否与系统实际一致
- 技术特点是否符合真实项目
- 代码文档是否需要把占位 Support 类替换为真实源码片段
