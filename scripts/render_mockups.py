#!/usr/bin/env python3
"""Render the 16 manual mockups as high-fidelity HTML pages screenshotted via Playwright.

All 16 images for one spec share a single palette derived from ``software_name``
so the bundle reads as a single product. Each scene maps to a Jinja HTML template
under ``templates/html/`` and is screenshotted at a fixed viewport.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import math
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates" / "html"


IMAGE_SIZES = {
    "image1.png":    (1600, 1000),
    "image2.jpeg":   (1440, 900),
    "image3.jpeg":   (1440, 900),
    "image4.jpeg":   (1440, 900),
    "image5.jpeg":   (1440, 900),
    "image6.jpeg":   (1440, 900),
    "image7.jpeg":   (1440, 900),
    "image8.jpeg":   (1440, 900),
    "image9.jpeg":   (1440, 900),
    "image10.jpeg":  (1440, 900),
    "image11.jpeg":  (1440, 900),
    "image12.jpeg":  (1440, 900),
    "image13.jpeg":  (1440, 900),
    "image14.jpeg":  (1440, 900),
    "image15.jpeg":  (1440, 900),
    "image16.jpeg":  (1440, 900),
}


SCENE_TEMPLATE = {
    "architecture":         "architecture.html.j2",
    "overview-home":        "dashboard.html.j2",
    "dashboard-overview":   "dashboard.html.j2",
    "dashboard-dimensions": "dashboard.html.j2",
    "overview-focus":       "list.html.j2",
    "search-result":        "list.html.j2",
    "manage-edit":          "list.html.j2",
    "manage-archive":       "list.html.j2",
    "record-edit":          "form.html.j2",
    "manage-create":        "form.html.j2",
    "record-success":       "success.html.j2",
    "search-input":         "search.html.j2",
    "search-filter":        "search.html.j2",
    "community-post":       "community.html.j2",
    "community-detail":     "community.html.j2",
    "community-reply":      "community.html.j2",
}


# ---------- palette ----------

def _hex(rgb: tuple[float, float, float]) -> str:
    r, g, b = (max(0, min(255, int(round(c * 255)))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def derive_palette(seed: str) -> dict:
    """One palette per software_name. All 16 images share it."""
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    hue = int(digest[:4], 16) % 360 / 360.0
    primary       = colorsys.hls_to_rgb(hue, 0.45, 0.62)
    primary_dark  = colorsys.hls_to_rgb(hue, 0.32, 0.66)
    primary_soft  = colorsys.hls_to_rgb(hue, 0.92, 0.55)
    accent        = colorsys.hls_to_rgb((hue + 0.55) % 1.0, 0.50, 0.55)
    return {
        "primary":      _hex(primary),
        "primary_dark": _hex(primary_dark),
        "primary_soft": _hex(primary_soft),
        "accent":       _hex(accent),
        "bg":           "#f4f6fa",
        "surface":      "#ffffff",
        "surface_2":    "#f8fafc",
        "border":       "#e5e7eb",
        "text":         "#1f2937",
        "text_muted":   "#6b7280",
    }


# ---------- shared context (sidebar / topbar / scene data) ----------

NAV_LABELS = [
    "工作台", "信息管理", "智能检索", "协同社区",
    "数据看板", "业务维护", "审批中心", "系统设置",
]

SCENE_NAV_INDEX = {
    "overview-home": 0, "overview-focus": 0,
    "record-edit": 1, "record-success": 1,
    "search-input": 2, "search-result": 2, "search-filter": 2,
    "community-post": 3, "community-detail": 3, "community-reply": 3,
    "dashboard-overview": 4, "dashboard-dimensions": 4,
    "manage-create": 5, "manage-edit": 5, "manage-archive": 5,
}

SCENE_BREADCRUMB = {
    "overview-home": "工作台",
    "overview-focus": "工作台 / 焦点事项",
    "record-edit": "信息管理 / 录入",
    "record-success": "信息管理 / 录入",
    "search-input": "智能检索 / 关键词",
    "search-result": "智能检索 / 结果",
    "search-filter": "智能检索 / 高级筛选",
    "community-post": "协同社区 / 全部话题",
    "community-detail": "协同社区 / 话题详情",
    "community-reply": "协同社区 / 回复管理",
    "dashboard-overview": "数据看板 / 总览",
    "dashboard-dimensions": "数据看板 / 多维分析",
    "manage-create": "业务维护 / 新建",
    "manage-edit": "业务维护 / 编辑",
    "manage-archive": "业务维护 / 归档",
}


def _short_name(name: str, limit: int = 10) -> str:
    return name if len(name) <= limit else name[:limit] + "…"


def _logo_letter(name: str) -> str:
    """Single CJK char or ascii initial."""
    for ch in name:
        if ch.strip():
            return ch
    return "S"


def _common_ctx(spec: dict, scene: str, label: str, palette: dict) -> dict:
    nav_idx = SCENE_NAV_INDEX.get(scene, 0)
    nav_items = [{"label": lbl, "active": i == nav_idx} for i, lbl in enumerate(NAV_LABELS)]
    return {
        "palette": palette,
        "software_name": spec["software_name"],
        "short_name": _short_name(spec["software_name"]),
        "logo_letter": _logo_letter(spec["software_name"]),
        "version": spec["version"],
        "industry": spec["industry"],
        "label": label,
        "page_desc": f"面向{spec['target_users']}，覆盖{spec['subject']}相关业务的操作入口。",
        "nav_items": nav_items,
        "breadcrumb": SCENE_BREADCRUMB.get(scene, "工作台"),
        "user_initial": "张",
        "user_name": "张管理员",
    }


def _dashboard_ctx(spec: dict, scene: str) -> dict:
    subject = spec["subject"]
    kpis = [
        {"label": f"{subject}总量",   "value": "1,284", "delta": "▲ 6.2% 较上周", "bar": 78},
        {"label": "待处理事项",       "value": "126",   "delta": "▲ 3 项",         "bar": 42},
        {"label": "本周新增",         "value": "318",   "delta": "▲ 12.4%",        "bar": 64},
        {"label": "异常告警",         "value": "5",     "delta": "▼ 2 项",         "bar": 18, "down": False},
    ]
    # smooth-ish curve
    ys = [160, 130, 145, 95, 110, 70, 85]
    xs = [50 + i * 60 for i in range(7)]
    chart_points = [{"x": x, "y": y} for x, y in zip(xs, ys)]
    chart_path = "M " + " L ".join(f"{x} {y}" for x, y in zip(xs, ys))
    chart_area = chart_path + f" L {xs[-1]} 200 L {xs[0]} 200 Z"
    side_rows = [
        {"name": f"{subject}重点", "count": 412, "pct": 62},
        {"name": "处理中事项",      "count": 268, "pct": 38},
        {"name": "已归档",          "count": 604, "pct": 84},
        {"name": "待复核",          "count":  86, "pct": 18},
    ]
    table_headers = ["编号", "名称", "负责人", "状态", "更新时间"]
    table_rows = [
        ["A-1284", f"{subject}季度复盘", "张明", {"tag": "success", "text": "已完成"}, "03-26 10:22"],
        ["A-1283", f"{subject}规范更新", "李欣", {"tag": "primary", "text": "进行中"}, "03-26 09:08"],
        ["A-1282", "客户回访任务",       "王强", {"tag": "warning", "text": "待跟进"}, "03-25 17:41"],
        ["A-1281", "运营数据校对",       "赵敏", {"tag": "neutral", "text": "待启动"}, "03-25 14:13"],
        ["A-1280", "异常工单复核",       "周晨", {"tag": "danger",  "text": "告警"},   "03-25 11:50"],
    ]
    return {
        "kpis": kpis,
        "chart_title": "近 7 日趋势" if scene == "overview-home" else "维度对比趋势",
        "chart_points": chart_points,
        "chart_path": chart_path,
        "chart_area": chart_area,
        "side_title": "分类占比",
        "side_rows": side_rows,
        "table_title": "最近活动",
        "table_headers": table_headers,
        "table_rows": table_rows,
    }


def _list_ctx(spec: dict, scene: str) -> dict:
    subject = spec["subject"]
    filters = [
        {"label": "分类", "options": [
            {"text": "全部", "on": True},
            {"text": f"{subject}重点"},
            {"text": "常规事项"},
            {"text": "归档"}]},
        {"label": "状态", "options": [
            {"text": "进行中", "on": True},
            {"text": "待审核"},
            {"text": "已完成"}]},
        {"label": "时间", "options": [
            {"text": "近 30 天", "on": True},
            {"text": "本季度"},
            {"text": "本年度"}]},
    ]
    rows = [
        ["A-2017", f"{subject}年度评估", "运营部", {"tag": "primary", "text": "进行中"}, "2026-03-26"],
        ["A-2016", "客户回访策划",       "市场部", {"tag": "warning", "text": "待审核"}, "2026-03-25"],
        ["A-2015", "标准操作流程修订",   "质控部", {"tag": "success", "text": "已发布"}, "2026-03-24"],
        ["A-2014", "异常事件复盘",       "技术部", {"tag": "danger",  "text": "告警"},   "2026-03-24"],
        ["A-2013", "供应商资质核验",     "采购部", {"tag": "neutral", "text": "归档"},   "2026-03-22"],
        ["A-2012", "季度数据对账",       "财务部", {"tag": "primary", "text": "进行中"}, "2026-03-21"],
        ["A-2011", "服务满意度调研",     "客服部", {"tag": "success", "text": "已发布"}, "2026-03-20"],
    ]
    return {
        "filters": filters,
        "table_title": "结果列表",
        "table_headers": ["编号", "名称", "归属部门", "状态", "更新时间"],
        "table_rows": rows,
        "total": 128,
    }


def _form_ctx(spec: dict, scene: str) -> dict:
    subject = spec["subject"]
    rows = [
        [
            {"label": "名称",     "required": True,  "type": "input",  "value": f"{subject}专项任务-2026Q2", "focus": True},
            {"label": "分类",     "required": True,  "type": "select", "value": "运营管理 ▾"},
        ],
        [
            {"label": "负责人",   "required": True,  "type": "select", "value": "张明 ▾"},
            {"label": "协办人员", "required": False, "type": "input",  "value": "李欣、王强、赵敏"},
        ],
        [
            {"label": "开始时间", "required": True,  "type": "input",  "value": "2026-04-01"},
            {"label": "截止时间", "required": True,  "type": "input",  "value": "2026-06-30", "hint": "可在截止前 7 天调整"},
        ],
    ]
    textarea = (
        f"围绕{spec['subject']}的关键场景，梳理流程节点与责任分工，"
        "并按周输出执行情况；如遇异常需在 24 小时内升级到部门负责人。"
    )
    return {
        "form_title": "信息录入" if scene == "record-edit" else "新建业务记录",
        "form_rows": rows,
        "textarea_label": "任务描述",
        "textarea_value": textarea,
    }


def _success_ctx(spec: dict, scene: str) -> dict:
    return {
        "success_title": "保存成功",
        "success_desc":  f"{spec['subject']}专项任务已记录，可在「业务维护」中查看。",
        "summary_items": [
            {"k": "记录编号", "v": "A-2018"},
            {"k": "提交人",   "v": "张管理员"},
            {"k": "提交时间", "v": "2026-03-26 11:32"},
            {"k": "审核流程", "v": "运营部 → 部门负责人 → 归档"},
        ],
        "recent_rows": [
            ["A-2018", f"{spec['subject']}专项任务-2026Q2", {"tag": "success", "text": "已保存"}, "11:32"],
            ["A-2017", "年度评估",                           {"tag": "primary", "text": "进行中"}, "10:22"],
            ["A-2016", "客户回访策划",                       {"tag": "warning", "text": "待审核"}, "09:08"],
        ],
    }


def _search_ctx(spec: dict, scene: str) -> dict:
    subject = spec["subject"]
    rows = [
        ["S-3022", f"{subject}应急预案 v3", "质控部", {"tag": "primary", "text": "发布"}, "2026-03-26"],
        ["S-3021", f"{subject}培训计划",     "人事部", {"tag": "success", "text": "归档"}, "2026-03-25"],
        ["S-3020", "客户档案核验报告",       "客服部", {"tag": "warning", "text": "待审"}, "2026-03-24"],
        ["S-3019", "数据对账模板",           "财务部", {"tag": "primary", "text": "发布"}, "2026-03-23"],
        ["S-3018", "运营周报-12 周",         "运营部", {"tag": "neutral", "text": "草稿"}, "2026-03-22"],
    ]
    return {
        "search_title": "高级检索",
        "search_query": f"{subject} AND 状态=进行中",
        "advanced": [
            {"label": "分类", "value": f"{subject}管理"},
            {"label": "状态", "value": "进行中"},
            {"label": "归属", "value": "全部部门"},
            {"label": "时间", "value": "2026-01 至 2026-03"},
        ],
        "table_headers": ["编号", "名称", "归属", "状态", "更新时间"],
        "table_rows": rows,
        "total": 28,
    }


def _community_ctx(spec: dict, scene: str) -> dict:
    subject = spec["subject"]
    posts = [
        {
            "author": "张明", "tag": "经验分享", "tag_type": "primary",
            "time": "2026-03-26 10:24",
            "title": f"{subject}业务自检清单 v2 分享",
            "excerpt": f"近期梳理了一份{subject}自检清单，覆盖准入、过程、复盘三类共 18 项要点，欢迎评论补充。",
            "replies": 12, "likes": 38,
        },
        {
            "author": "李欣", "tag": "求助讨论", "tag_type": "warning",
            "time": "2026-03-26 09:08",
            "title": "跨部门协同时如何避免重复录入？",
            "excerpt": "我们在两个班次衔接时经常出现重复录入，想看看大家在系统里都用了哪些规则、模板或自动化方式。",
            "replies": 7, "likes": 14,
        },
        {
            "author": "王强", "tag": "公告", "tag_type": "success",
            "time": "2026-03-25 17:41",
            "title": "本周线上培训 - 数据看板新维度",
            "excerpt": "本周五 16:00 线上培训，主题为数据看板新增的多维分析能力，会有问答环节，欢迎报名。",
            "replies": 5, "likes": 22,
        },
        {
            "author": "赵敏", "tag": "Bug 反馈", "tag_type": "danger",
            "time": "2026-03-25 14:13",
            "title": "导出 Excel 时偶现空行",
            "excerpt": "复现条件：勾选筛选条件后再切换分类标签时，导出文件首行有时为空。已附环境信息与截图。",
            "replies": 9, "likes": 6,
        },
    ]
    topics = [
        {"name": f"{subject}标准化", "count": 86},
        {"name": "跨部门协同",       "count": 64},
        {"name": "数据看板用法",     "count": 51},
        {"name": "客户回访技巧",     "count": 42},
        {"name": "异常处置经验",     "count": 33},
    ]
    return {"feed_title": "全部话题", "posts": posts, "side_title": "热门话题", "topics": topics}


def _architecture_ctx(spec: dict, palette: dict) -> dict:
    arch = spec.get("architecture", {})
    return {
        "palette": palette,
        "software_name": spec["software_name"],
        "subtitle": arch.get("subtitle") or "前后端分离 · 分层架构",
        "layers": arch.get("layers", []),
    }


SCENE_CTX_BUILDER = {
    "overview-home":        _dashboard_ctx,
    "dashboard-overview":   _dashboard_ctx,
    "dashboard-dimensions": _dashboard_ctx,
    "overview-focus":       _list_ctx,
    "search-result":        _list_ctx,
    "manage-edit":          _list_ctx,
    "manage-archive":       _list_ctx,
    "record-edit":          _form_ctx,
    "manage-create":        _form_ctx,
    "record-success":       _success_ctx,
    "search-input":         _search_ctx,
    "search-filter":        _search_ctx,
    "community-post":       _community_ctx,
    "community-detail":     _community_ctx,
    "community-reply":      _community_ctx,
}


def _render_html(spec: dict, scene: str, label: str, palette: dict, env: Environment) -> str:
    template_name = SCENE_TEMPLATE.get(scene, "dashboard.html.j2")
    template = env.get_template(template_name)
    if scene == "architecture":
        return template.render(**_architecture_ctx(spec, palette))
    ctx = _common_ctx(spec, scene, label, palette)
    ctx.update(SCENE_CTX_BUILDER[scene](spec, scene))
    return template.render(**ctx)


def render_mockups(spec: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    palette = derive_palette(spec["software_name"])
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    # Import inside the function so a missing Playwright install errors with a
    # clear actionable message only when this code path is actually used.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for the HTML→screenshot pipeline. "
            "Install with: pip install playwright && playwright install chromium"
        ) from exc

    created: list[Path] = []
    html_dir = output_dir / "_html"
    html_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for item in spec["image_plan"]:
                filename = item["filename"]
                width, height = IMAGE_SIZES[filename]
                html = _render_html(spec, item["scene"], item["label"], palette, env)
                (html_dir / f"{Path(filename).stem}.html").write_text(html, encoding="utf-8")

                page = browser.new_page(
                    viewport={"width": width, "height": height},
                    device_scale_factor=1.0,
                )
                page.set_content(html, wait_until="load")
                # Settle layout for any async font metrics.
                page.wait_for_timeout(120)
                out_path = output_dir / filename
                if out_path.suffix.lower() == ".png":
                    page.screenshot(path=str(out_path), type="png", full_page=False, clip={
                        "x": 0, "y": 0, "width": width, "height": height,
                    })
                else:
                    page.screenshot(path=str(out_path), type="jpeg", quality=90, full_page=False, clip={
                        "x": 0, "y": 0, "width": width, "height": height,
                    })
                page.close()
                created.append(out_path)
        finally:
            browser.close()

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Render high-fidelity HTML mockups via Playwright.")
    parser.add_argument("--spec", required=True, help="Path to spec JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for generated images")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    render_mockups(spec, Path(args.output_dir))


if __name__ == "__main__":
    main()
