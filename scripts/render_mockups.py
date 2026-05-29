#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


IMAGE_SIZES = {
    "image1.png": (1920, 755),
    "image2.jpeg": (1920, 1080),
    "image3.jpeg": (1920, 1080),
    "image4.jpeg": (1920, 1119),
    "image5.jpeg": (1920, 1151),
    "image6.jpeg": (1920, 1080),
    "image7.jpeg": (1920, 1080),
    "image8.jpeg": (1920, 1080),
    "image9.jpeg": (1920, 1284),
    "image10.jpeg": (1920, 1677),
    "image11.jpeg": (1920, 1725),
    "image12.jpeg": (1920, 1080),
    "image13.jpeg": (1920, 1080),
    "image14.jpeg": (1920, 1080),
    "image15.jpeg": (1920, 1080),
    "image16.jpeg": (1920, 1080),
}

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Songti.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def theme_color(seed: str) -> tuple[int, int, int]:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    hue = int(digest[:2], 16)
    if hue < 85:
        return (29, 78, 216)
    if hue < 170:
        return (5, 150, 105)
    return (217, 119, 6)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill, radius: int = 24, outline=None):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if draw.textlength(candidate, font=font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def draw_browser_frame(draw, width, height, title, accent):
    rounded(draw, (40, 32, width - 40, height - 32), fill=(247, 248, 251), radius=30, outline=(225, 229, 235))
    rounded(draw, (40, 32, width - 40, 108), fill=(255, 255, 255), radius=30, outline=(225, 229, 235))
    for idx, color in enumerate(((239, 68, 68), (234, 179, 8), (34, 197, 94))):
        draw.ellipse((72 + idx * 34, 58, 94 + idx * 34, 80), fill=color)
    draw.text((180, 54), title, fill=(31, 41, 55), font=load_font(30))
    rounded(draw, (60, 130, 340, height - 60), fill=accent, radius=28)
    draw.text((92, 170), "系统导航", fill="white", font=load_font(28))
    items = ["首页总览", "信息录入", "智能检索", "互动协作", "数据统计", "业务管理"]
    item_bg = tuple(max(0, c - 40) for c in accent)
    for idx, item in enumerate(items):
        y = 240 + idx * 82
        rounded(draw, (78, y, 320, y + 54), fill=item_bg, radius=18)
        draw.text((102, y + 12), item, fill="white", font=load_font(24))
    return 380, 140, width - 70, height - 70


def draw_cards(draw, box, accent, labels):
    left, top, right, _ = box
    width = right - left
    card_w = (width - 60) // 3
    for idx, label in enumerate(labels):
        x0 = left + idx * (card_w + 30)
        rounded(draw, (x0, top, x0 + card_w, top + 150), fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
        draw.text((x0 + 28, top + 28), label, fill=(71, 85, 105), font=load_font(24))
        draw.text((x0 + 28, top + 78), f"{(idx + 2) * 128}", fill=accent, font=load_font(40))


def draw_table(draw, box, headers, rows):
    left, top, right, bottom = box
    rounded(draw, box, fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
    row_height = 70
    col_width = (right - left - 40) // len(headers)
    for idx, header in enumerate(headers):
        x = left + 20 + idx * col_width
        draw.text((x, top + 18), header, fill=(71, 85, 105), font=load_font(24))
    for row_idx, row in enumerate(rows):
        y = top + 70 + row_idx * row_height
        draw.line((left + 20, y - 12, right - 20, y - 12), fill=(241, 245, 249), width=2)
        for col_idx, value in enumerate(row):
            x = left + 20 + col_idx * col_width
            draw.text((x, y + 8), value, fill=(51, 65, 85), font=load_font(22))
        if y + row_height > bottom:
            break


def draw_chart(draw, box, accent):
    left, top, right, bottom = box
    rounded(draw, box, fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
    points = []
    steps = 6
    for idx in range(steps):
        x = left + 70 + idx * ((right - left - 140) / (steps - 1))
        phase = idx / 2.0
        y = bottom - 90 - int((math.sin(phase) + 1.4) * 90)
        points.append((x, y))
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=accent)
    draw.line(points, fill=accent, width=6)
    for idx in range(4):
        y = top + 60 + idx * ((bottom - top - 120) / 3)
        draw.line((left + 40, y, right - 40, y), fill=(241, 245, 249), width=2)


def draw_architecture_diagram(draw: ImageDraw.ImageDraw, width: int, height: int, spec: dict, accent: tuple[int, int, int]) -> None:
    rounded(draw, (60, 60, width - 60, height - 60), fill=(255, 255, 255), radius=32, outline=(226, 232, 240))
    title = f"{spec['software_name']} 系统架构图"
    draw.text((100, 90), title, fill=(17, 24, 39), font=load_font(40))
    draw.text((100, 142), "前后端分离 · 分层架构 · Spring Boot + Vue + MySQL", fill=(100, 116, 139), font=load_font(22))

    accent_light = tuple(min(255, c + 80) for c in accent)
    accent_dark = tuple(max(0, c - 35) for c in accent)
    neutral_bg = (248, 250, 252)
    box_outline = (203, 213, 225)

    layer_x0, layer_x1 = 100, width - 100
    layer_h = 90
    layer_gap = 22
    top_y = 200

    def draw_layer(y: int, title_text: str, items: list[str], header_color):
        rounded(draw, (layer_x0, y, layer_x1, y + layer_h), fill=neutral_bg, radius=20, outline=box_outline)
        rounded(draw, (layer_x0, y, layer_x0 + 220, y + layer_h), fill=header_color, radius=20)
        draw.text((layer_x0 + 28, y + 28), title_text, fill="white", font=load_font(26))
        usable_left = layer_x0 + 260
        usable_right = layer_x1 - 30
        if not items:
            return
        cell_w = (usable_right - usable_left - (len(items) - 1) * 16) // len(items)
        for idx, item in enumerate(items):
            x0 = usable_left + idx * (cell_w + 16)
            x1 = x0 + cell_w
            rounded(draw, (x0, y + 18, x1, y + layer_h - 18), fill=(255, 255, 255), radius=14, outline=box_outline)
            text_w = draw.textlength(item, font=load_font(22))
            draw.text((x0 + max(12, (cell_w - text_w) // 2), y + 28), item, fill=(31, 41, 55), font=load_font(22))

    layers = [
        ("用户层", ["PC 浏览器", "移动端浏览器", "管理后台"], accent),
        ("前端层", ["Vue 3 + TypeScript", "Vue Router", "Pinia 状态管理", "Element Plus UI"], accent_dark),
        ("接口层", ["Nginx 反向代理", "Spring Boot REST API", "鉴权与限流过滤器"], accent),
        ("业务服务层", ["总览服务", "录入服务", "检索服务", "协作服务", "统计服务", "管理服务"], accent_dark),
        ("数据访问层", ["MyBatis Plus", "事务管理", "数据校验"], accent),
        ("数据与基础设施", ["MySQL", "Redis 缓存", "文件存储", "日志服务"], accent_dark),
    ]

    available_height = height - 60 - top_y - 60
    layer_h = max(70, (available_height - layer_gap * (len(layers) - 1)) // len(layers))

    y = top_y
    for layer_title, items, header_color in layers:
        draw_layer(y, layer_title, items, header_color)
        if y + layer_h + layer_gap < height - 80:
            arrow_x = (layer_x0 + layer_x1) // 2
            draw.line((arrow_x, y + layer_h + 2, arrow_x, y + layer_h + layer_gap - 2), fill=accent, width=4)
            draw.polygon(
                [(arrow_x - 8, y + layer_h + layer_gap - 6), (arrow_x + 8, y + layer_h + layer_gap - 6), (arrow_x, y + layer_h + layer_gap + 4)],
                fill=accent,
            )
        y += layer_h + layer_gap


def draw_scene(image: Image.Image, spec: dict, scene: str, label: str):
    draw = ImageDraw.Draw(image)
    accent = theme_color(spec["software_name"])
    width, height = image.size
    draw.rectangle((0, 0, width, height), fill=(237, 242, 247))
    if scene == "overview-flow":
        draw_architecture_diagram(draw, width, height, spec, accent)
        return
    content_box = draw_browser_frame(draw, width, height, label, accent)
    left, top, right, bottom = content_box
    draw.text((left + 16, top), label, fill=(15, 23, 42), font=load_font(34))
    if scene in {"overview-home", "dashboard-overview"}:
        draw_cards(draw, (left, top + 70, right, top + 220), accent, ["总量", "待处理", "本周新增"])
        draw_chart(draw, (left, top + 260, right - 350, bottom), accent)
        draw_table(draw, (right - 320, top + 260, right, bottom), ["分类", "数量"], [["重点", "128"], ["处理中", "56"], ["已归档", "32"]])
    elif scene in {"overview-focus", "search-result", "manage-edit"}:
        draw_table(draw, (left, top + 70, right - 20, bottom - 20), ["编号", "名称", "状态", "更新时间"], [["A-1001", "核心条目", "ACTIVE", "03-26"], ["A-1002", "重点事项", "PENDING", "03-25"], ["A-1003", "历史记录", "DONE", "03-24"], ["A-1004", "协同任务", "ACTIVE", "03-23"]])
    elif scene in {"record-edit", "manage-create"}:
        rounded(draw, (left, top + 70, right - 20, bottom - 20), fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
        labels = ["名称", "分类", "负责人", "时间", "描述", "附件"]
        for idx, text in enumerate(labels):
            y = top + 110 + idx * 110
            draw.text((left + 36, y), text, fill=(71, 85, 105), font=load_font(24))
            rounded(draw, (left + 180, y - 10, right - 60, y + 48), fill=(248, 250, 252), radius=16, outline=(203, 213, 225))
        rounded(draw, (left + 180, top + 110 + 5 * 110 - 10, right - 60, top + 110 + 5 * 110 + 160), fill=(248, 250, 252), radius=16, outline=(203, 213, 225))
        rounded(draw, (right - 220, bottom - 100, right - 60, bottom - 40), fill=accent, radius=18)
        draw.text((right - 180, bottom - 87), "保存提交", fill="white", font=load_font(24))
    elif scene in {"record-success", "manage-archive"}:
        draw_table(draw, (left, top + 70, right - 20, bottom - 20), ["编号", "名称", "状态", "操作"], [["R-2001", "示例条目", "已保存", "查看"], ["R-2002", "待审核项", "处理中", "编辑"], ["R-2003", "归档项", "已归档", "恢复"]])
        rounded(draw, (left + 280, top + 200, right - 280, top + 430), fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
        draw.text((left + 360, top + 250), "操作成功", fill=accent, font=load_font(40))
        draw.text((left + 360, top + 318), "当前记录已完成保存并同步更新列表。", fill=(71, 85, 105), font=load_font(24))
    elif scene in {"search-input", "search-filter"}:
        rounded(draw, (left, top + 70, right - 20, top + 150), fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
        rounded(draw, (left + 24, top + 92, right - 220, top + 128), fill=(248, 250, 252), radius=16, outline=(203, 213, 225))
        draw.text((left + 42, top + 96), "输入名称、编号或关键词", fill=(148, 163, 184), font=load_font(22))
        rounded(draw, (right - 190, top + 82, right - 42, top + 136), fill=accent, radius=18)
        draw.text((right - 150, top + 95), "开始检索", fill="white", font=load_font(24))
        draw_table(draw, (left, top + 190, right - 20, bottom - 20), ["筛选项", "取值", "说明"], [["分类", "全部", "支持下拉筛选"], ["状态", "处理中", "可多选"], ["时间", "近30天", "支持范围查询"]])
    elif scene in {"community-post", "community-detail", "community-reply"}:
        rounded(draw, (left, top + 70, right - 20, bottom - 20), fill=(255, 255, 255), radius=24, outline=(226, 232, 240))
        y = top + 110
        for idx in range(4):
            rounded(draw, (left + 26, y, right - 46, y + 160), fill=(248, 250, 252), radius=18, outline=(226, 232, 240))
            draw.text((left + 50, y + 24), f"主题讨论 {idx + 1}", fill=(15, 23, 42), font=load_font(26))
            lines = wrap_text(draw, "围绕业务流转、数据维护和协同处理展开交流反馈，支持评论、回复与状态跟进。", load_font(22), right - left - 160)
            for line_idx, text in enumerate(lines[:2]):
                draw.text((left + 50, y + 70 + line_idx * 34), text, fill=(71, 85, 105), font=load_font(22))
            y += 190
    else:
        draw_table(draw, (left, top + 70, right - 20, bottom - 20), ["字段", "内容", "状态"], [["名称", spec["software_name"], "已配置"], ["版本", spec["version"], "已配置"], ["行业", spec["industry"], "已配置"]])


def render_mockups(spec: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for item in spec["image_plan"]:
        size = IMAGE_SIZES[item["filename"]]
        image = Image.new("RGB", size, (255, 255, 255))
        draw_scene(image, spec, item["scene"], item["label"])
        path = output_dir / item["filename"]
        if path.suffix.lower() == ".png":
            image.save(path, format="PNG")
        else:
            image.save(path, format="JPEG", quality=92)
        created.append(path)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Render screenshot-style mockups for the manual template.")
    parser.add_argument("--spec", required=True, help="Path to spec JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for generated images")
    args = parser.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    render_mockups(spec, Path(args.output_dir))


if __name__ == "__main__":
    main()
