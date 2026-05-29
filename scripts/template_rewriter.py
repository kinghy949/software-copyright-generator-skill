#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path


GENERIC_SUFFIXES = (
    "综合管理平台", "服务管理平台", "业务管理平台", "管理平台", "服务平台",
    "信息平台", "服务系统", "管理系统", "信息系统", "客户端", "小程序",
    "网站", "平台", "系统", "软件", "应用",
)

INDUSTRY_RULES = (
    ("校园", "教育信息化", "高校师生及校内管理人员"),
    ("高校", "教育信息化", "高校师生及校内管理人员"),
    ("医院", "医疗健康", "医护人员、管理人员及服务对象"),
    ("医疗", "医疗健康", "医护人员、管理人员及服务对象"),
    ("物业", "物业管理", "物业服务人员、业主及管理人员"),
    ("社区", "社区服务", "社区居民、服务人员及管理人员"),
    ("农业", "现代农业", "农业从业人员及农业管理人员"),
    ("政务", "政务服务", "办事群众及政务工作人员"),
    ("企业", "企业服务", "企业员工、业务人员及管理人员"),
    ("电商", "电子商务", "商家、平台运营人员及消费者"),
    ("物流", "物流供应链", "业务人员、调度人员及管理人员"),
    ("志愿", "校园服务", "组织者、参与者及后台管理人员"),
)

MODULE_PAGES = [5, 7, 9, 12, 15, 17]
MODULE_TITLES = ["总览首页", "信息录入", "智能检索", "互动协作", "后台数据统计", "业务管理"]
MODULE_SCENES = [
    ["overview-home", "overview-focus"],
    ["record-edit", "record-success"],
    ["search-input", "search-result", "search-filter"],
    ["community-post", "community-detail", "community-reply"],
    ["dashboard-overview", "dashboard-dimensions"],
    ["manage-create", "manage-edit", "manage-archive"],
]


def collapse_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", text).strip() or "未命名系统"


def pick_subject(software_name: str, intro: str) -> str:
    name = re.sub(r"^基于[^的]{1,20}的", "", collapse_text(software_name))
    for suffix in GENERIC_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            name = name[: -len(suffix)]
            break
    name = name.strip("《》()（）-_ ")
    chinese = re.findall(r"[\u4e00-\u9fff]{2,16}", name)
    if chinese:
        return chinese[0][:10]
    english = re.findall(r"[A-Za-z0-9]+", software_name)
    if english:
        return " ".join(english[:2])
    intro_words = re.findall(r"[\u4e00-\u9fff]{2,16}", intro)
    return intro_words[0][:8] if intro_words else "业务"


def build_package_slug(software_name: str, intro: str) -> str:
    english = re.findall(r"[A-Za-z0-9]+", f"{software_name} {intro}".lower())
    filtered = [word for word in english if word not in {"web", "system", "platform", "app", "service", "management", "manage"}]
    if filtered:
        return re.sub(r"[^a-z0-9]+", "-", "-".join(filtered[:3])).strip("-")[:24] or "softcopy"
    digest = hashlib.sha1(f"{software_name}|{intro}".encode("utf-8")).hexdigest()[:8]
    return f"softcopy-{digest}"


def pick_industry_and_users(software_name: str, intro: str) -> tuple[str, str]:
    context = f"{software_name}{intro}"
    for keyword, industry, users in INDUSTRY_RULES:
        if keyword in context:
            return industry, users
    return "通用信息服务", "业务用户、运营人员及后台管理人员"


def sentence(text: str) -> str:
    text = collapse_text(text)
    if not text:
        return ""
    return text if text.endswith(("。", "！", "？")) else f"{text}。"


def build_modules(subject: str) -> list[dict]:
    return [
        {
            "index": idx + 1,
            "title": ("后台数据统计" if base == "后台数据统计" else f"{subject}{base}"),
            "toc_page": MODULE_PAGES[idx],
            "groups": groups,
        }
        for idx, (base, groups) in enumerate(
            [
                ("总览首页", [("浏览总览与快捷入口", 2), ("查看重点内容", 2)]),
                ("信息录入", [("填写基础信息", 3), ("提交保存与状态回显", 3)]),
                ("智能检索", [("输入检索条件", 2), ("执行搜索并查看结果", 2), ("多维筛选与排序", 2)]),
                ("互动协作", [("发布协作内容", 2), ("查看详情与发表评论", 2), ("进行楼层回复与跟进", 2)]),
                ("后台数据统计", [("查看总览数据", 2), ("切换分析维度", 2)]),
                ("业务管理", [("新建业务条目", 2), ("编辑现有数据", 2), ("下架或归档条目", 2)]),
            ]
        )
    ]


def _build_purpose(subject: str) -> str:
    text = f"提升{subject}业务的信息化处理效率，规范数据录入、查询与统计协同。"
    return text if len(text) <= 50 else text[:49] + "。"


def _build_main_features(subject: str, industry: str, target_users: str) -> str:
    paragraphs = [
        f"本软件面向{industry}领域的{target_users}，围绕{subject}相关业务构建统一的数字化处理与协同管理入口，"
        f"在功能层面覆盖首页总览、信息录入、智能检索、互动协作、数据统计与业务管理六大核心模块，"
        f"形成从信息采集、查询定位、协同处理到统计分析的完整闭环。",
        f"首页总览模块以卡片化和可视化方式集中展示{subject}核心业务指标、待办提醒与最新动态，"
        f"用户登录后即可在统一界面把握业务运行态势，并通过快捷入口直接跳转到对应功能页面，"
        f"显著降低不同功能之间的切换成本。",
        f"信息录入模块面向{subject}业务对象提供结构化表单与附件上传能力，"
        f"在录入过程中执行必填项校验、格式校验与状态回显，保证数据规范完整；"
        f"系统同步生成唯一编号并写入业务列表，便于后续追踪与维护。",
        f"智能检索模块支持关键词搜索、联想提示、分类筛选、时间范围过滤与多字段排序，"
        f"用户可在大量{subject}业务数据中快速定位目标记录，"
        f"并通过结果详情面板查看完整字段信息，提升业务处理效率。",
        f"互动协作模块以主题发布、详情查看、评论回复和楼层跟进为主线，"
        f"支持{target_users}围绕业务问题进行交流反馈与经验共享，"
        f"系统对协作过程进行留痕和状态追踪，便于业务事项的持续推进。",
        f"后台数据统计模块面向管理员构建数据大屏，通过指标卡片、折线图、柱状图和饼图展示"
        f"{subject}业务的整体规模、分布特征和趋势变化，支持时间维度切换与指标联动分析，"
        f"为日常运营和管理决策提供直观依据。",
        f"业务管理模块统一维护{subject}相关业务条目，覆盖新建、编辑、上下架、归档和状态流转等"
        f"常见操作，配合权限控制与操作日志，确保业务数据的稳定性、可追溯性和长期可维护性。",
    ]
    text = "".join(paragraphs)
    if len(text) > 1300:
        text = text[:1299] + "。"
    return text


def build_spec(software_name: str, intro: str, version: str = "V1.0") -> dict:
    subject = pick_subject(software_name, intro)
    industry, target_users = pick_industry_and_users(software_name, intro)
    digest = hashlib.sha1(f"{software_name}|{intro}".encode("utf-8")).hexdigest()[:6]
    modules = build_modules(subject)
    intro_text = sentence(intro) or sentence(
        f"本系统围绕{subject}相关业务提供统一入口，支持信息录入、查询统计、协同处理和后台管理。"
    )
    return {
        "software_name": collapse_text(software_name),
        "safe_software_name": safe_filename(software_name),
        "subject": subject,
        "version": version,
        "intro": intro_text[:140] + ("" if len(intro_text) <= 140 else "。"),
        "industry": industry,
        "target_users": target_users,
        "purpose": _build_purpose(subject),
        "main_features": _build_main_features(subject, industry, target_users),
        "technical_highlights": sentence(
            "平台采用 Spring Boot 与 Vue 的前后端分离架构，具备清晰的模块边界、稳定的数据访问能力和良好的界面响应体验"
        ),
        "development_date": date.today().strftime("%Y年%m月%d日"),
        "package_slug": build_package_slug(software_name, intro),
        "package_name": f"com.generated.{build_package_slug(software_name, intro).replace('-', '')}",
        "class_prefix": f"Softcopy{digest.capitalize()}",
        "flow_text": sentence(
            f"用户登录系统后，可先在{subject}总览首页查看核心指标和待办入口，再进入信息录入模块维护业务数据，通过智能检索快速定位目标记录，并在互动协作模块完成反馈交流和处理跟进；后台管理人员可进一步使用数据统计页面查看整体运行情况，并在业务管理模块中进行创建、编辑和归档操作"
        ),
        "modules": modules,
        "defaults": {
            "rights_acquisition": "原始取得",
            "rights_scope": "全部权利",
            "software_type": "应用软件",
            "software_nature": "原创",
            "development_mode": "单独开发",
            "publication_status": "未发表",
            "dev_hardware": "Intel i7-12700H, 16GB RAM",
            "run_hardware": "Intel i5-12400, 8GB RAM",
            "dev_os": "Windows 11",
            "dev_tools": "IntelliJ IDEA, Maven, Git, Node.js",
            "run_platform": "Windows 10/11, macOS",
            "support_software": "Java 17, Spring Boot 3, MySQL, Vue 3",
            "languages": "Java, HTML, CSS, JavaScript, TypeScript, SQL, XML",
        },
        "image_plan": [
            {"filename": "image1.png", "scene": "overview-flow", "label": "系统架构图"},
            {"filename": "image2.jpeg", "scene": "overview-home", "label": modules[0]["title"]},
            {"filename": "image3.jpeg", "scene": "overview-focus", "label": f"{modules[0]['title']}详情"},
            {"filename": "image4.jpeg", "scene": "record-edit", "label": modules[1]["title"]},
            {"filename": "image5.jpeg", "scene": "record-success", "label": f"{modules[1]['title']}提交"},
            {"filename": "image6.jpeg", "scene": "search-input", "label": modules[2]["title"]},
            {"filename": "image7.jpeg", "scene": "search-result", "label": f"{modules[2]['title']}结果"},
            {"filename": "image8.jpeg", "scene": "search-filter", "label": f"{modules[2]['title']}筛选"},
            {"filename": "image9.jpeg", "scene": "community-post", "label": modules[3]["title"]},
            {"filename": "image10.jpeg", "scene": "community-detail", "label": f"{modules[3]['title']}详情"},
            {"filename": "image11.jpeg", "scene": "community-reply", "label": f"{modules[3]['title']}回复"},
            {"filename": "image12.jpeg", "scene": "dashboard-overview", "label": modules[4]["title"]},
            {"filename": "image13.jpeg", "scene": "dashboard-dimensions", "label": f"{modules[4]['title']}维度"},
            {"filename": "image14.jpeg", "scene": "manage-create", "label": modules[5]["title"]},
            {"filename": "image15.jpeg", "scene": "manage-edit", "label": f"{modules[5]['title']}编辑"},
            {"filename": "image16.jpeg", "scene": "manage-archive", "label": f"{modules[5]['title']}归档"},
        ],
    }


def build_manual_sequence(spec: dict) -> list[str]:
    subject = spec["subject"]
    modules = spec["modules"]
    def toc_line(title: str, page: int, indent: int = 0) -> str:
        prefix = "    " * indent
        dot_count = max(3, 48 - len(prefix) - len(title) - len(str(page)))
        return f"{prefix}{title} {'.' * dot_count} {page}"

    texts = [
        "操作手册", f"基于Java&Vue的{spec['software_name']} {spec['version']}", "目录",
        toc_line("一、软件简介", 3),
        toc_line("二、业务流程与使用说明", 4),
        toc_line("2.1 系统架构与整体业务流程", 4, indent=1),
        toc_line("2.2 功能模块说明", 5, indent=1),
    ]
    texts.extend([toc_line(f"2.2.{m['index']} {m['title']}", m['toc_page'], indent=2) for m in modules])
    architecture_text = sentence(
        "系统采用前后端分离的分层架构：前端基于 Vue 3 与 TypeScript 构建可复用组件，"
        "通过 Nginx 反向代理与 Spring Boot REST 接口进行通信；后端按业务服务层、"
        "数据访问层和数据与基础设施层划分，下游统一对接 MySQL 数据库、Redis 缓存、"
        "文件存储和日志服务，整体结构清晰、职责单一、便于扩展"
    )
    texts.extend(["一、软件简介", spec["intro"], "二、业务流程与使用说明", "2.1 系统架构与整体业务流程", architecture_text, spec["flow_text"], "2.2 功能模块说明"])
    line_map = {
        "浏览总览与快捷入口": [
            "用户进入页面后，先查看顶部关键指标卡片与中央内容列表，快速了解当前业务状态和最新数据变化。",
            "用户点击页面中的快捷入口按钮后，界面立即跳转至对应功能模块，实现从首页到业务页的快速流转。",
        ],
        "查看重点内容": [
            "用户在推荐区域点击某条重点记录后，右侧详情面板即时展开，展示该条数据的摘要信息与处理状态。",
            "用户根据页面提示继续执行查看、收藏或进入详情等操作，系统同步更新当前浏览状态并保持页面反馈清晰。",
        ],
        "填写基础信息": [
            "用户点击页面中的录入按钮进入编辑界面，在表单中依次填写名称、分类、时间和描述等基础字段。",
            "用户在输入过程中，系统同步执行必填项检查与格式校验，并以高亮提示的方式反馈当前填写状态。",
            "用户如需补充资料，可在附件区域上传图片或文档，系统在右侧区域立即生成对应预览内容。",
        ],
        "提交保存与状态回显": [
            "用户点击保存按钮提交数据后，系统在后台完成字段校验、编号生成和状态记录，并显示加载动画。",
            "当校验通过后，页面弹出保存成功提示框，同时将当前记录同步写入列表区域，便于后续继续维护。",
            "若存在缺失字段或格式异常，系统在对应输入项下方即时标记问题位置，方便用户快速修正后再次提交。",
        ],
        "输入检索条件": [
            "用户将光标置于页面顶部搜索框内，输入与业务对象相关的名称、编号或关键描述信息。",
            "系统根据已输入内容在下拉区域中实时展示联想词条和最近搜索记录，辅助用户快速锁定检索目标。",
        ],
        "执行搜索并查看结果": [
            "用户按下回车键或点击搜索按钮后，结果列表区域立即刷新，展示符合条件的记录摘要与核心字段。",
            "用户点击任意结果卡片后，系统在详情面板中展开该条数据的完整信息，便于进一步核对和处理。",
        ],
        "多维筛选与排序": [
            "用户在左侧筛选区勾选分类、状态、时间或标签条件后，页面内容即时根据组合规则重新计算并展示。",
            "用户通过排序控件切换时间优先、热度优先或状态优先等展示方式，系统同步刷新列表顺序和分页结果。",
        ],
        "发布协作内容": [
            "用户在顶部编辑区域输入标题、正文和补充说明后，可结合业务场景上传图片或附件作为内容补充。",
            "用户点击发布按钮后，系统将新内容即时插入列表顶部，并在界面中反馈发布时间、发布人和处理状态。",
        ],
        "查看详情与发表评论": [
            "用户在列表区域选择某条主题后，页面立即展开详情面板，显示完整正文、附件信息和历史评论内容。",
            "用户在评论框中输入反馈意见后点击提交，系统实时追加评论内容并同步更新当前主题的互动计数。",
        ],
        "进行楼层回复与跟进": [
            "用户点击指定评论下方的回复入口后，界面在当前楼层附近展开输入区域，便于定向沟通。",
            "用户完成回复后，系统按照时间顺序展示楼层链路，并保留上下文信息以支持后续持续跟进。",
        ],
        "查看总览数据": [
            "管理员进入统计页面后，首先查看顶部指标卡片、中央趋势图以及业务分布概览，快速掌握整体运行情况。",
            "管理员切换时间范围后，页面中的关键指标与趋势图会同步刷新，直观呈现不同周期下的数据变化特征。",
        ],
        "切换分析维度": [
            "管理员点击左侧分析导航中的不同维度后，中央图表区平滑切换为对应的统计视图与明细列表。",
            "管理员将鼠标悬停在图表元素上时，系统即时弹出详细数值、占比信息和辅助说明，便于深入分析。",
        ],
        "新建业务条目": [
            "管理员点击新建按钮后，界面切换至编辑模式，在表单区录入标题、时间、负责人和详细说明等内容。",
            "管理员填写完成后点击保存，系统即时将新条目加入列表，并同步展示当前状态、编号和更新时间。",
        ],
        "编辑现有数据": [
            "管理员在列表中点击编辑入口后，系统加载该条记录的历史信息，并以可编辑表单形式展示在右侧区域。",
            "管理员修改字段后确认保存，页面会立即刷新对应行内容，同时保留操作反馈和最近变更记录。",
        ],
        "下架或归档条目": [
            "管理员点击下架或归档按钮后，系统弹出确认对话框，提示当前操作对展示范围和流程状态的影响。",
            "管理员确认后，条目状态即时变更为禁用或归档，列表区域同步更新标签颜色和筛选结果。",
        ],
    }
    summary_map = {
        modules[0]["title"]: f"该页面作为{subject}业务的统一入口，集中展示最新动态、待办提醒和快捷操作区。通过卡片式布局和状态标签，帮助用户快速掌握系统核心信息，并进入高频功能页面。",
        modules[1]["title"]: f"此功能模块用于录入和维护{subject}相关核心数据，界面由表单区、附件区和实时校验提示区组成。通过结构化字段和即时反馈机制，保障录入内容的规范性、完整性和后续可追踪性。",
        modules[2]["title"]: f"该页面提供针对{subject}数据的多条件检索能力，支持关键词搜索、分类筛选、时间范围过滤和结果排序。页面布局突出检索框、筛选面板和结果区，便于用户在大量业务数据中快速定位目标信息。",
        modules[3]["title"]: f"该模块用于围绕{subject}业务开展交流反馈、经验共享和协同处理，页面采用列表与详情联动的交互方式。通过主题发布、评论回复和状态追踪机制，提升用户之间的信息协作效率。",
        modules[4]["title"]: f"该页面面向管理员展示{subject}系统运行态势与业务分布情况，通过卡片、折线图、柱状图和饼图构建数据大屏。系统支持时间维度切换与指标联动分析，为管理决策提供直观依据。",
        modules[5]["title"]: f"该模块用于统一维护{subject}相关业务条目，支持创建、编辑、上下架和状态流转等常见管理动作。界面采用列表与表单双区结构，并通过状态标签和操作按钮提升业务维护效率。",
    }
    for module in modules:
        texts.extend([f"2.2.{module['index']} {module['title']}", summary_map[module["title"]], "操作步骤："])
        for group_idx, (group_title, _) in enumerate(module["groups"], start=1):
            texts.append(f"2.2.{module['index']}.{group_idx} {group_title}")
            for step_idx, line in enumerate(line_map[group_title], start=1):
                texts.append(f"（{step_idx}）{line}")
    return texts


def build_code_lines(spec: dict, min_non_empty_lines: int = 3200) -> list[str]:
    pkg = spec["package_name"]
    prefix = spec["class_prefix"]
    lines = [
        f"package {pkg};", "", "import org.springframework.boot.SpringApplication;",
        "import org.springframework.boot.autoconfigure.SpringBootApplication;", "",
        "@SpringBootApplication", f"public class {prefix}Application {{",
        "    public static void main(String[] args) {",
        f"        SpringApplication.run({prefix}Application.class, args);", "    }", "}", "",
    ]
    module_codes = ["Portal", "Record", "Search", "Community", "Dashboard", "Manage"]
    for module, code in zip(spec["modules"], module_codes):
        class_name = f"{prefix}{code}"
        lower = code.lower()
        chinese = module["title"]
        bundle = [
            f"package {pkg}.domain;", "", "import java.time.LocalDateTime;", "",
            f"public class {class_name}Entity {{", "    private Long id;", "    private String code;",
            "    private String name;", "    private String category;", "    private String status;",
            "    private String owner;", "    private String description;", "    private LocalDateTime createdAt;",
            "    private LocalDateTime updatedAt;", "}", "",
            f"package {pkg}.dto;", "", f"public record {class_name}DTO(",
            "    Long id, String code, String name, String category, String status,",
            "    String owner, String description, String updatedAt) { }", "",
            f"package {pkg}.service;", "", "import java.util.List;", "import java.util.ArrayList;", "",
            f"public class {class_name}Service {{", f"    public List<{class_name}DTO> list(String keyword) {{",
            f"        List<{class_name}DTO> rows = new ArrayList<>();", "        if (keyword == null) { keyword = \"\"; }",
            "        for (int i = 0; i < 20; i++) {",
            f"            rows.add(new {class_name}DTO((long) i, \"{code.upper()}-\" + i, keyword + \"{chinese}\", \"默认分类\", \"ACTIVE\", \"system\", \"自动生成示例数据\", \"2026-03-26 10:00:00\"));",
            "        }", "        return rows;", "    }",
            f"    public {class_name}DTO detail(Long id) {{",
            f"        return new {class_name}DTO(id, \"{code.upper()}-\" + id, \"{chinese}详情\", \"重点\", \"ACTIVE\", \"system\", \"详情数据\", \"2026-03-26 10:00:00\");",
            "    }",
            f"    public {class_name}DTO create({class_name}DTO request) {{ return request; }}",
            f"    public {class_name}DTO update(Long id, {class_name}DTO request) {{ return request; }}",
            "    public void archive(Long id) { System.out.println(id); }", "}", "",
            f"package {pkg}.controller;", "", "import java.util.List;", "",
            f"public class {class_name}Controller {{", f"    private final {class_name}Service service = new {class_name}Service();",
            f"    public List<{class_name}DTO> list(String keyword) {{ return service.list(keyword); }}",
            f"    public {class_name}DTO detail(Long id) {{ return service.detail(id); }}",
            f"    public {class_name}DTO create({class_name}DTO request) {{ return service.create(request); }}",
            f"    public {class_name}DTO update(Long id, {class_name}DTO request) {{ return service.update(id, request); }}",
            "    public void archive(Long id) { service.archive(id); }", "}", "",
            f"// Vue 页面片段: {chinese}", "<template>", "  <div class=\"page-wrapper\">",
            "    <el-input placeholder=\"请输入关键词\" />", "    <el-button type=\"primary\">查询</el-button>",
            "    <el-button>新建</el-button>", "    <el-table :data=\"rows\">",
            "      <el-table-column prop=\"code\" label=\"编号\" />",
            "      <el-table-column prop=\"name\" label=\"名称\" />",
            "      <el-table-column prop=\"status\" label=\"状态\" />", "    </el-table>", "  </div>",
            "</template>", "", "<script setup lang=\"ts\">", "import { ref } from 'vue';",
            f"const rows = ref<{class_name}DTO[]>([]);", "function loadData(): void { rows.value = rows.value.slice(); }",
            "</script>", "", f"-- SQL Schema: {chinese}",
            f"CREATE TABLE IF NOT EXISTS tb_{spec['package_slug'].replace('-', '_')}_{lower} (",
            "    id BIGINT PRIMARY KEY AUTO_INCREMENT, code VARCHAR(64), name VARCHAR(128),",
            "    category VARCHAR(64), status VARCHAR(32), owner VARCHAR(64), description TEXT,",
            "    created_at DATETIME, updated_at DATETIME", ");", "",
        ]
        lines.extend(bundle)
    support_index = 1
    while sum(1 for line in lines if line.strip()) < min_non_empty_lines:
        lines.extend([
            f"package {pkg}.support;", "", "import java.util.ArrayList;", "import java.util.List;", "",
            f"public class {prefix}Support{support_index:03d} {{", "    private final List<String> logs = new ArrayList<>();",
            "    public void append(String message) { logs.add(message); }",
            "    public List<String> snapshot() { return new ArrayList<>(logs); }",
            "    public boolean contains(String keyword) { return logs.stream().anyMatch(item -> item.contains(keyword)); }",
            "    public String exportText() { return String.join(\"\\n\", logs); }", "}", "",
        ])
        support_index += 1
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Build soft copyright draft content spec.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--intro", required=True)
    parser.add_argument("--version", default="V1.0")
    parser.add_argument("--output")
    args = parser.parse_args()
    spec = build_spec(args.name, args.intro, args.version)
    content = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
