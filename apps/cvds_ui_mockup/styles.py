"""
styles.py - 复刻 cvds_cpp_detector/MainWindow.cpp 中 setStyleSheet() 的颜色与字号。
所有颜色、字号、间距与 Qt 源文件 1:1 对应（避免重复数字，便于以后直接改这里再出图）。

用法：from styles import COLORS, FONT_FAMILY, FONT_PIXEL_BASE; 然后 PIL 用 COLORS['xxx']。
"""

# 主色板（取自 MainWindow.cpp setStyleSheet 第 1173 行起）
COLORS = {
    "root_bg":        "#0B1118",
    "panel_bg":       "#151C24",
    "panel_dark":     "#111B25",
    "panel_darker":   "#080D13",
    "panel_mid":      "#0B1118",
    "border":         "#263746",
    "border_strong":  "#31485B",
    "text":           "#F3F7FA",
    "text_mid":       "#DCE7EE",
    "text_dim":       "#B8C8D4",
    "text_muted":     "#8FA5B8",
    "text_subtle":    "#708395",
    "text_faint":     "#536574",
    "text_disabled":  "#536574",
    "primary":        "#2F88F5",
    "primary_hover":  "#4DA3FF",
    "primary_dark":   "#173B63",
    "danger_bg":      "#4A2024",
    "danger_hover":   "#67282F",
    "danger_border":  "#8D343C",
    "danger_text":    "#FFDDE0",
    "danger_signal":  "#F25555",
    "ok_bg":          "#10251F",
    "ok_border":      "#245B47",
    "ok_text":        "#36C98F",
    "select_bg":      "#172431",
    "table_header":   "#172431",
    "scroll_bg":      "#0B1118",
    "scroll_handle":  "#3A4D5E",
    "scroll_hover":   "#4DA3FF",
    "field_bg":       "#0B1118",
    "field_pressed":  "#21364A",
    "input_focus":    "#4DA3FF",
    "check_box":      "#0B1118",
    "check_border":   "#3A5367",
    "check_checked":  "#2F88F5",
    "video_surface":  "#080D13",
    "splitter":       "#172431",
    "splitter_hover": "#2F88F5",
    "jam_jam_text":   "#FFDDE0",
    "empty_bg":       "#0B1118",
    "empty_text":     "#708395",
    "header_text":    "#F3F7FA",
}

# 字体（Win 上是 "Microsoft YaHei UI"，Linux 用 Noto Sans CJK 等价）
FONT_FAMILY_PRIMARY = "Noto Sans CJK SC"
FONT_FAMILY_FALLBACK = "DejaVu Sans"

# 基础字号（与 MainWindow.cpp resizeSidebarToStitchRatio 中 11–14 像素一致）
FONT_PIXEL_BASE = 12
FONT_PIXEL_KPI_TITLE = 9
FONT_PIXEL_KPI_VALUE = 18
FONT_PIXEL_BADGE = 9
FONT_PIXEL_SECTION_TITLE = 12
FONT_PIXEL_SECTION_SUBTITLE = 8
FONT_PIXEL_SUBTITLE = 9
FONT_PIXEL_TABLE_CELL = 11
FONT_PIXEL_NAV = 11

# 间距
PADDING = 8
SIDEBAR_RATIO = 0.17  # 与 MainWindow.cpp resizeSidebarToStitchRatio 中 17/100 一致
SIDEBAR_MIN = 250
SIDEBAR_MAX = 320
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800
