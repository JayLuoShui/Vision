"""
ui_preview.py - 用 Pillow 复刻 CVDS C++ Detector 主窗口，模拟 setStyleSheet 渲染。

设计原则：
- 1:1 颜色、字号、间距照搬 MainWindow.cpp setStyleSheet
- 不仿真 OpenCV 视频流（用纯色 + 文字占位）
- 输出 PNG 1280x800 模拟 maximized 状态

运行：
    python3 ui_preview.py render baseline.png
    python3 ui_preview.py render --out custom.png
"""
import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
from styles import (  # noqa: E402
    COLORS, DEFAULT_HEIGHT, DEFAULT_WIDTH, FONT_FAMILY_FALLBACK,
    FONT_FAMILY_PRIMARY, FONT_PIXEL_BADGE, FONT_PIXEL_BASE, FONT_PIXEL_KPI_TITLE,
    FONT_PIXEL_KPI_VALUE, FONT_PIXEL_NAV, FONT_PIXEL_SECTION_SUBTITLE,
    FONT_PIXEL_SECTION_TITLE, FONT_PIXEL_SUBTITLE, FONT_PIXEL_TABLE_CELL,
    PADDING, SIDEBAR_MAX, SIDEBAR_MIN, SIDEBAR_RATIO,
)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """优先 Noto Sans CJK（中文），失败回退 DejaVu Sans。
    真实 Qt 端会回退到 Microsoft YaHei UI，但视觉上无差别。"""
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    """Pillow 8+ 兼容 textbbox/textlength 差异。"""
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except AttributeError:
        return draw.textlength(text, font=font), font.size


def _draw_text_centered(
    draw: ImageDraw.ImageDraw, xy_box, text, font, fill, bold=False
):
    """在 xy_box=(x, y, w, h) 内水平+垂直居中绘制文本。"""
    x, y, w, h = xy_box
    tw, th = _text_size(draw, text, font)
    tx = x + (w - tw) // 2
    ty = y + (h - th) // 2 - 2  # -2 是 baseline 微调
    draw.text((tx, ty), text, fill=fill, font=font)


def _rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


# ==== 组件 ====

def draw_brand_bar(draw, x, y, w, h, fonts):
    """顶栏品牌栏 QFrame#brandBar。"""
    _rounded_rect(
        draw, (x, y, x + w, y + h), radius=3,
        fill=COLORS["panel_dark"], outline=COLORS["border"], width=1,
    )
    # 左侧 logo 占位（用深色方块模拟图片）
    logo_size = h - 6
    _rounded_rect(
        draw, (x + 4, y + 3, x + 4 + logo_size, y + 3 + logo_size),
        radius=2, fill=COLORS["primary"],
    )
    draw.text(
        (x + 4 + logo_size + 8, y + 5),
        "CVDS  ·  在线包裹流量监测",
        fill=COLORS["text"], font=fonts["title"],
    )
    draw.text(
        (x + 4 + logo_size + 8, y + h - 14),
        "COGY  AI  Vision  Platform",
        fill=COLORS["text_muted"], font=fonts["subtitle"],
    )
    # 右侧徽标
    badges = [
        ("2.4.1",        COLORS["text_dim"],    COLORS["border"]),
        ("●  已就绪",     COLORS["ok_text"],     COLORS["ok_border"]),
    ]
    bx = x + w - 10
    for text, tcolor, bcolor in badges:
        bw, bh = _text_size(draw, text, fonts["badge"])
        bx -= bw + 16
        _rounded_rect(
            draw, (bx, y + 5, bx + bw + 14, y + h - 5),
            radius=3, fill=COLORS["select_bg"], outline=bcolor, width=1,
        )
        _draw_text_centered(
            draw, (bx, y + 5, bw + 14, h - 10),
            text, fonts["badge"], tcolor,
        )


def draw_sidebar_panel(draw, x, y, w, h, fonts, active_idx=0):
    """左侧设置面板 QWidget#settingsPanel。"""
    # 面板背景
    draw.rectangle((x, y, x + w, y + h), fill=COLORS["panel_bg"])
    # 顶栏 sidebarHeader
    header_h = 38
    draw.rectangle((x, y, x + w, y + header_h), fill=COLORS["panel_dark"])
    draw.line(
        (x, y + header_h, x + w, y + header_h),
        fill=COLORS["border"], width=1,
    )
    draw.text(
        (x + 10, y + 7), "控制面板",
        fill=COLORS["text"], font=fonts["title"],
    )
    draw.text(
        (x + 10, y + 23), "SETTINGS",
        fill=COLORS["text_subtle"], font=fonts["section_subtitle"],
    )

    # 6 个导航按钮
    nav_items = ["模型", "视频源", "输出", "推理参数", "区域", "控制"]
    nav_h = 30
    cur_y = y + header_h + 1
    for i, label in enumerate(nav_items):
        active = (i == active_idx)
        if active:
            draw.rectangle(
                (x, cur_y, x + w, cur_y + nav_h),
                fill=COLORS["select_bg"],
            )
            # 左侧 3px 蓝色边
            draw.rectangle(
                (x, cur_y, x + 3, cur_y + nav_h),
                fill=COLORS["primary"],
            )
            draw.text(
                (x + 14, cur_y + 7), label,
                fill=COLORS["text"], font=fonts["nav"],
            )
        else:
            draw.text(
                (x + 14, cur_y + 7), label,
                fill=COLORS["text_dim"], font=fonts["nav"],
            )
        cur_y += nav_h

    # 分隔
    cur_y += 4
    draw.line(
        (x + 6, cur_y, x + w - 6, cur_y),
        fill=COLORS["border"], width=1,
    )
    cur_y += 8

    return _draw_path_panel(draw, x, cur_y, w, h - (cur_y - y), fonts)


def _draw_path_panel(draw, x, y, w, h, fonts):
    """3 个 QGroupBox：模型 / 视频源 / 输出。"""
    # QGroupBox 边框
    def _groupbox(gy, title):
        gh = 78
        draw.rounded_rectangle(
            (x + 4, gy, x + w - 4, gy + gh),
            radius=5, fill=COLORS["panel_dark"],
            outline=COLORS["border"], width=1,
        )
        # 标题 (QGroupBox::title)
        draw.text(
            (x + 14, gy - 6), title,
            fill=COLORS["text_muted"], font=fonts["section_subtitle"],
        )
        return gy + gh

    # 模型 group
    draw.text((x + 12, y + 8), "后端", fill=COLORS["text_dim"], font=fonts["body"])
    draw.rounded_rectangle(
        (x + 80, y + 4, x + w - 10, y + 22),
        radius=4, fill=COLORS["field_bg"], outline=COLORS["border"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 4, w - 90, 18),
        "OpenVINO  ▼",
        fonts["body"], COLORS["text"],
    )
    draw.text((x + 12, y + 30), "模型", fill=COLORS["text_dim"], font=fonts["body"])
    draw.rounded_rectangle(
        (x + 80, y + 26, x + w - 10, y + 44),
        radius=4, fill=COLORS["field_bg"], outline=COLORS["border"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 26, w - 90, 18),
        "yolo26s-seg-wds-1024-best.xml",
        fonts["body"], COLORS["text_muted"],
    )
    draw.rounded_rectangle(
        (x + 80, y + 50, x + w - 80, y + 68),
        radius=4, fill=COLORS["select_bg"],
        outline=COLORS["border_strong"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 50, w - 160, 18),
        "选择模型",
        fonts["body"], COLORS["text_mid"],
    )
    y = _groupbox(y, "  模型")
    y += 4

    # 视频源 group
    draw.text((x + 12, y + 8), "视频源", fill=COLORS["text_dim"], font=fonts["body"])
    draw.rounded_rectangle(
        (x + 80, y + 4, x + w - 10, y + 22),
        radius=4, fill=COLORS["field_bg"], outline=COLORS["border"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 4, w - 90, 18),
        "rtsp://admin@192.168.1.64:554/Streaming/...",
        fonts["body"], COLORS["text_muted"],
    )
    draw.rounded_rectangle(
        (x + 80, y + 26, x + (x + w) // 2 - 4, y + 44),
        radius=4, fill=COLORS["select_bg"],
        outline=COLORS["border_strong"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 26, (w - 8) // 2 - 88, 18),
        "应用视频流",
        fonts["body"], COLORS["primary_hover"],
    )
    draw.rounded_rectangle(
        (x + (x + w) // 2, y + 26, x + w - 10, y + 44),
        radius=4, fill=COLORS["select_bg"],
        outline=COLORS["border_strong"], width=1,
    )
    _draw_text_centered(
        draw, (x + (x + w) // 2, y + 26, w - (x + w) // 2 + x - 90, 18),
        "测试视频流",
        fonts["body"], COLORS["primary_hover"],
    )
    y = _groupbox(y, "  视频源")
    y += 4

    # 输出 group
    draw.text((x + 12, y + 8), "输出目录", fill=COLORS["text_dim"], font=fonts["body"])
    draw.rounded_rectangle(
        (x + 80, y + 4, x + w - 10, y + 22),
        radius=4, fill=COLORS["field_bg"], outline=COLORS["border"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 4, w - 90, 18),
        "D:/Demo/Vision/runs/cvds",
        fonts["body"], COLORS["text_muted"],
    )
    draw.rounded_rectangle(
        (x + 80, y + 26, x + w - 10, y + 44),
        radius=4, fill=COLORS["select_bg"],
        outline=COLORS["border_strong"], width=1,
    )
    _draw_text_centered(
        draw, (x + 80, y + 26, w - 90, 18),
        "选择输出目录",
        fonts["body"], COLORS["text_mid"],
    )
    y = _groupbox(y, "  输出")
    y += 6
    return y


def draw_main_splitter(draw, x, y, w, h, fonts):
    """右侧主面板：splitter handle + 监控画布 + KPI。"""
    # 监控标题栏
    title_h = 24
    draw.rectangle((x, y, x + w, y + h), fill=COLORS["panel_darker"])
    draw.rectangle((x, y, x + w, y + title_h), fill=COLORS["panel_dark"])
    draw.line(
        (x, y + title_h, x + w, y + title_h),
        fill=COLORS["border"], width=1,
    )
    draw.text(
        (x + 10, y + 5), "实时监控",
        fill=COLORS["text"], font=fonts["body"],
    )
    draw.text(
        (x + 80, y + 6), "  ROI: 已配置 1 个区域",
        fill=COLORS["text_muted"], font=fonts["subtitle"],
    )
    return y + title_h


def draw_monitor_canvas(draw, x, y, w, h, fonts):
    """QFrame#monitorPanel 中间的视频画面。"""
    # 视频面背景
    draw.rectangle((x, y, x + w, y + h), fill=COLORS["video_surface"])
    # 模拟视频 placeholder
    placeholder_w = w // 2
    placeholder_h = h // 2
    px = x + (w - placeholder_w) // 2
    py = y + (h - placeholder_h) // 2
    draw.rectangle(
        (px, py, px + placeholder_w, py + placeholder_h),
        outline=COLORS["border"], width=1,
    )
    _draw_text_centered(
        draw, (px, py, placeholder_w, placeholder_h),
        "[  实时视频流  ]\n  ●  已连接 192.168.1.64  ●  25 fps",
        fonts["body"], COLORS["text_subtle"],
    )

    # 模拟 ROI 矩形（绿色半透明框）
    roi_x, roi_y, roi_w, roi_h = x + 60, y + 80, 320, 200
    draw.rectangle(
        (roi_x, roi_y, roi_x + roi_w, roi_y + roi_h),
        outline=COLORS["ok_text"], width=2,
    )
    draw.text(
        (roi_x + 6, roi_y + 4), "main_in",
        fill=COLORS["ok_text"], font=fonts["subtitle"],
    )


def draw_kpi_strip(draw, x, y, w, h, fonts):
    """KPI 卡片条 QFrame#dashboardStrip。"""
    kpis = [
        ("累计包裹",     "0",   COLORS["primary"]),
        ("系统状态",     "已就绪", COLORS["ok_text"]),
        ("区域内目标",   "0",   COLORS["primary"]),
        ("累计堵包",     "0",   COLORS["primary"]),
    ]
    cell_w = w // 4
    for i, (title, value, color) in enumerate(kpis):
        cx = x + i * cell_w + 4
        cy = y + 4
        cw = cell_w - 8
        ch = h - 8
        # QFrame#dashboardCard
        _rounded_rect(
            draw, (cx, cy, cx + cw, cy + ch), radius=3,
            fill=COLORS["panel_dark"], outline=COLORS["border"], width=1,
        )
        # 左侧 2px 蓝色
        draw.rectangle(
            (cx, cy, cx + 2, cy + ch), fill=color,
        )
        # 标题
        draw.text(
            (cx + 12, cy + 6), title,
            fill=COLORS["text_muted"], font=fonts["kpi_title"],
        )
        # 数值
        if value.isdigit():
            draw.text(
                (cx + 12, cy + 22), value,
                fill=COLORS["text"], font=fonts["kpi_value"],
            )
        else:
            draw.text(
                (cx + 12, cy + 24), value,
                fill=COLORS["ok_text"], font=fonts["kpi_value_small"],
            )


def draw_region_panel(draw, x, y, w, h, fonts):
    """区域统计表 QFrame#regionPanel。"""
    title_h = 24
    draw.rectangle((x, y, x + w, y + h), fill=COLORS["panel_darker"])
    draw.rectangle((x, y, x + w, y + title_h), fill=COLORS["panel_dark"])
    draw.line(
        (x, y + title_h, x + w, y + title_h),
        fill=COLORS["border"], width=1,
    )
    draw.text(
        (x + 10, y + 5), "区域统计",
        fill=COLORS["text"], font=fonts["body"],
    )
    draw.text(
        (x + 90, y + 6), "  1 个监测区域  ·  当前看板: main_in",
        fill=COLORS["text_muted"], font=fonts["subtitle"],
    )
    # 展开/收起按钮 (右上)
    btn_w = 78
    btn_x = x + w - btn_w - 8
    _rounded_rect(
        draw, (btn_x, y + 4, btn_x + btn_w, y + title_h - 4),
        radius=3, fill=COLORS["select_bg"],
        outline=COLORS["border"], width=1,
    )
    _draw_text_centered(
        draw, (btn_x, y + 4, btn_w, title_h - 8),
        "收起统计", fonts["subtitle"], COLORS["text_dim"],
    )

    # 表格头
    ty = y + title_h + 1
    headers = ["区域", "累计", "内", "状态", "堵包秒", "堵包次"]
    col_w = [w - 360, 50, 50, 80, 70, 70, 50][0:6]
    # 自适应列宽
    total_fixed = 50 + 50 + 80 + 70 + 70 + 50
    first_col = w - 16 - total_fixed
    widths = [first_col, 50, 50, 80, 70, 70, 50][0:6]
    # 表头底
    draw.rectangle(
        (x, ty, x + w, ty + 24), fill=COLORS["table_header"],
    )
    cx = x + 6
    for i, h_text in enumerate(headers):
        draw.text(
            (cx, ty + 6), h_text,
            fill=COLORS["text_muted"], font=fonts["table"],
        )
        cx += widths[i]
    # 行
    ry = ty + 24
    row_h = 26
    draw.rectangle(
        (x, ry, x + w, ry + row_h),
        fill=COLORS["select_bg"],  # 选中行（main_in 是当前看板）
    )
    cx = x + 6
    cells = [
        ("main_in  (当前看板)", COLORS["text"]),
        ("0",  COLORS["text"]),
        ("0",  COLORS["text"]),
        ("空闲", COLORS["text_dim"]),
        ("0.0", COLORS["text_dim"]),
        ("0",  COLORS["text_dim"]),
    ]
    for i, (text, color) in enumerate(cells):
        draw.text(
            (cx, ry + 6), text,
            fill=color, font=fonts["table"],
        )
        cx += widths[i]


def draw_action_dock(draw, x, y, w, h, fonts):
    """底部动作区 QFrame#actionDock。"""
    draw.rectangle((x, y, x + w, y + h), fill=COLORS["panel_dark"])
    # 蓝色顶边
    draw.rectangle((x, y, x + w, y + 2), fill=COLORS["primary"])

    btn_h = 38
    btn_y = y + 8
    # 主按钮
    btn_w = w // 3 - 8
    btn_x = x + 6
    _rounded_rect(
        draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
        radius=4, fill=COLORS["primary"], outline=COLORS["primary_hover"], width=1,
    )
    _draw_text_centered(
        draw, (btn_x, btn_y, btn_w, btn_h),
        "▶  开始检测",
        fonts["body_bold"], COLORS["text"],
    )
    # 危险按钮
    btn_x = x + 12 + btn_w
    _rounded_rect(
        draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
        radius=4, fill=COLORS["danger_bg"], outline=COLORS["danger_border"], width=1,
    )
    _draw_text_centered(
        draw, (btn_x, btn_y, btn_w, btn_h),
        "■  停止检测",
        fonts["body_bold"], COLORS["danger_text"],
    )
    # 次按钮
    btn_x = x + 18 + 2 * btn_w
    _rounded_rect(
        draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h),
        radius=4, fill=COLORS["select_bg"],
        outline=COLORS["border_strong"], width=1,
    )
    _draw_text_centered(
        draw, (btn_x, btn_y, btn_w, btn_h),
        "⚙  运行环境自检",
        fonts["body"], COLORS["text_mid"],
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["render"])
    parser.add_argument("--out", default=str(THIS / "baseline.png"))
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--active-nav", type=int, default=0,
                        help="高亮导航项索引 0-5（默认 0 = 模型）")
    args = parser.parse_args()

    # 字体
    fonts = {
        "title":              _load_font(FONT_PIXEL_SECTION_TITLE),
        "body":               _load_font(FONT_PIXEL_BASE),
        "body_bold":          _load_font(FONT_PIXEL_BASE + 1),
        "subtitle":           _load_font(FONT_PIXEL_SUBTITLE),
        "section_subtitle":   _load_font(FONT_PIXEL_SECTION_SUBTITLE),
        "kpi_title":          _load_font(FONT_PIXEL_KPI_TITLE),
        "kpi_value":          _load_font(FONT_PIXEL_KPI_VALUE),
        "kpi_value_small":    _load_font(FONT_PIXEL_KPI_VALUE - 4),
        "nav":                _load_font(FONT_PIXEL_NAV),
        "table":              _load_font(FONT_PIXEL_TABLE_CELL),
        "badge":              _load_font(FONT_PIXEL_BADGE),
    }

    img = Image.new("RGB", (args.width, args.height), COLORS["root_bg"])
    draw = ImageDraw.Draw(img)

    # 顶栏
    brand_h = 38
    draw_brand_bar(
        draw, x=PADDING, y=PADDING, w=args.width - 2 * PADDING, h=brand_h,
        fonts=fonts,
    )

    # 主内容区
    content_y = brand_h + 2 * PADDING
    content_h = args.height - content_y - PADDING

    # 左右分割
    sidebar_w = max(
        SIDEBAR_MIN,
        min(SIDEBAR_MAX, int(args.width * SIDEBAR_RATIO)),
    )
    main_x = PADDING
    main_w = args.width - 2 * PADDING

    # 左侧：控制面板
    draw_sidebar_panel(
        draw, x=main_x, y=content_y, w=sidebar_w, h=content_h,
        fonts=fonts, active_idx=args.active_nav,
    )

    # 右侧：splitter handle + 监控 + KPI + 区域表
    right_x = main_x + sidebar_w + 2
    right_w = main_w - sidebar_w - 2
    # splitter 把手
    draw.rectangle(
        (right_x - 1, content_y, right_x, content_y + content_h),
        fill=COLORS["splitter"],
    )

    # 上：监控面板
    monitor_h = int(content_h * 0.65)
    monitor_y = draw_main_splitter(
        draw, x=right_x, y=content_y, w=right_w, h=monitor_h, fonts=fonts,
    )
    draw_monitor_canvas(
        draw, x=right_x, y=monitor_y, w=right_w, h=monitor_h - 24, fonts=fonts,
    )

    # 中：KPI 卡片条
    kpi_h = 56
    kpi_y = content_y + monitor_h
    draw_kpi_strip(
        draw, x=right_x, y=kpi_y, w=right_w, h=kpi_h, fonts=fonts,
    )

    # 中下：区域统计表
    region_h = 110
    region_y = kpi_y + kpi_h + 6
    draw_region_panel(
        draw, x=right_x, y=region_y, w=right_w, h=region_h, fonts=fonts,
    )

    # 底：动作区
    action_h = 56
    action_y = content_y + content_h - action_h
    draw_action_dock(
        draw, x=right_x, y=action_y, w=right_w, h=action_h, fonts=fonts,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    print(f"saved {out} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
