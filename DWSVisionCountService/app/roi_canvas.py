"""Tkinter ROI 图片选择和绘制面板。"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from app.config import Config
from app.roi_editor import EditMode, ROIEditorState


MODE_LABELS: dict[str, EditMode] = {
    "检测矩形": "detect_rect",
    "输送带多边形": "belt_polygon",
    "忽略矩形": "ignore_rect",
}


class ROIEditorPanel(ttk.Frame):
    """把经过测试的 ROI 状态模型连接到 Tk Canvas。"""

    def __init__(self, parent: tk.Misc, config: Config):
        super().__init__(parent, padding=16)
        self.config = config
        self.image_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.photo_image: ImageTk.PhotoImage | None = None
        self.state: ROIEditorState | None = None
        self.drag_start: tuple[float, float] | None = None
        self.preview_rect: int | None = None
        self.mode_var = tk.StringVar(value="检测矩形")
        self.image_var = tk.StringVar(value="尚未选择现场图片")
        self.hint_var = tk.StringVar(value="选择图片后开始标定")
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="绘制模式").pack(side="left")
        mode = ttk.Combobox(
            toolbar,
            textvariable=self.mode_var,
            values=list(MODE_LABELS),
            state="readonly",
            width=14,
        )
        mode.pack(side="left", padx=(8, 0))
        mode.bind("<<ComboboxSelected>>", self._on_mode_changed)
        ttk.Button(toolbar, text="选择图片", command=self._select_image).pack(
            side="left",
            padx=(14, 0),
        )
        ttk.Label(
            toolbar,
            textvariable=self.image_var,
            width=36,
            anchor="w",
        ).pack(side="left", padx=(10, 0))

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(10, 10))
        ttk.Button(actions, text="完成多边形", command=self._finish_polygon).pack(side="left")
        ttk.Button(actions, text="撤销", command=self._undo).pack(
            side="left",
            padx=(8, 0),
        )
        ttk.Button(actions, text="清空当前", command=self._clear_current).pack(
            side="left",
            padx=(8, 0),
        )
        ttk.Label(actions, textvariable=self.hint_var).pack(side="right")

        self.canvas = tk.Canvas(
            self,
            bg="#111c2b",
            highlightthickness=1,
            highlightbackground="#263a52",
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.after_idle(self._render)

        legend = ttk.Frame(self)
        legend.pack(fill="x", pady=(10, 0))
        ttk.Label(legend, text="橙色：检测区域").pack(side="left")
        ttk.Label(legend, text="青色：输送带 ROI").pack(side="left", padx=(18, 0))
        ttk.Label(legend, text="红色：忽略区域").pack(side="left", padx=(18, 0))

    def _select_image(self) -> None:
        path = filedialog.askopenfilename(
            title="选择现场图片",
            filetypes=[
                ("图片", "*.jpg *.jpeg *.png *.bmp"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.load_image(Path(path))

    def load_image(self, path: Path) -> None:
        try:
            image = Image.open(path).convert("RGB")
            state = ROIEditorState(
                image_size=image.size,
                canvas_size=self._canvas_size(),
                mode=MODE_LABELS[self.mode_var.get()],
            )
            state.load_existing(
                detect_rect=self.config.get_roi_rect(),
                belt_polygon=[tuple(point) for point in self.config.belt_polygon],
                ignore_rects=[
                    (region.x1, region.y1, region.x2, region.y2)
                    for region in self.config.ignore_regions
                ],
            )
        except ValueError as exc:
            if not messagebox.askyesno(
                "ROI 尺寸不匹配",
                f"{exc}\n\n是否按整张图片重新初始化 ROI？原配置在保存前不会改变。",
            ):
                return
            width, height = image.size
            state = ROIEditorState(
                image_size=image.size,
                canvas_size=self._canvas_size(),
                mode=MODE_LABELS[self.mode_var.get()],
            )
            state.load_existing(
                detect_rect=(0, 0, width, height),
                belt_polygon=[
                    (0, 0),
                    (width, 0),
                    (width, height),
                    (0, height),
                ],
                ignore_rects=[],
            )
        except Exception as exc:
            messagebox.showerror("图片加载失败", str(exc))
            return

        self.image_path = path
        self.source_image = image
        self.state = state
        self.image_var.set(f"{path.name}  |  {image.width} × {image.height}")
        self.hint_var.set(self._mode_hint())
        self._render()

    def region_values(
        self,
    ) -> tuple[
        int,
        int,
        tuple[int, int, int, int],
        tuple[tuple[int, int], ...],
        tuple[tuple[int, int, int, int], ...],
    ]:
        if self.state is None:
            return (
                self.config.camera.raw_width,
                self.config.camera.raw_height,
                self.config.get_roi_rect(),
                tuple(tuple(point) for point in self.config.belt_polygon),
                tuple(
                    (region.x1, region.y1, region.x2, region.y2)
                    for region in self.config.ignore_regions
                ),
            )
        detect = tuple(self.state.export("detect_rect"))
        polygon = tuple(tuple(point) for point in self.state.export("belt_polygon"))
        ignores = tuple(tuple(rect) for rect in self.state.export("ignore_rect"))
        width, height = self.state.transform.image_size
        return width, height, detect, polygon, ignores

    def apply_config(self, config: Config) -> None:
        self.config = config

    def _canvas_size(self) -> tuple[int, int]:
        return max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())

    def _on_mode_changed(self, _event=None) -> None:
        if self.state is not None:
            self.state.set_mode(MODE_LABELS[self.mode_var.get()])
        self.hint_var.set(self._mode_hint())

    def _mode_hint(self) -> str:
        mode = MODE_LABELS[self.mode_var.get()]
        if mode == "belt_polygon":
            return "逐点单击，至少三个点"
        return "按住鼠标拖动绘制矩形"

    def _finish_polygon(self) -> None:
        if self.state is None:
            messagebox.showwarning("尚未选择图片", "请先选择现场图片")
            return
        try:
            points = self.state.export("belt_polygon")
        except ValueError as exc:
            messagebox.showerror("多边形未完成", str(exc))
            return
        self.hint_var.set(f"输送带多边形已完成，共 {len(points)} 个点")
        self._render()

    def _undo(self) -> None:
        if self.state is not None and self.state.undo():
            self._render()

    def _clear_current(self) -> None:
        if self.state is None:
            return
        self.state.clear()
        self._render()

    def _on_canvas_resize(self, _event=None) -> None:
        if self.state is not None:
            self.state.set_canvas_size(self._canvas_size())
            self._render()

    def _on_press(self, event: tk.Event) -> None:
        if self.state is None:
            return
        point = (float(event.x), float(event.y))
        if self.state.mode == "belt_polygon":
            try:
                self.state.add_point(point)
            except ValueError:
                return
            self._render()
            return
        try:
            self.state.transform.canvas_to_image(point)
        except ValueError:
            return
        self.drag_start = point

    def _on_drag(self, event: tk.Event) -> None:
        if self.drag_start is None or self.state is None:
            return
        point = (float(event.x), float(event.y))
        try:
            self.state.transform.canvas_to_image(point)
        except ValueError:
            return
        if self.preview_rect is not None:
            self.canvas.delete(self.preview_rect)
        color = "#ffb000" if self.state.mode == "detect_rect" else "#ff5c5c"
        self.preview_rect = self.canvas.create_rectangle(
            *self.drag_start,
            *point,
            outline=color,
            width=2,
            dash=(6, 4),
        )

    def _on_release(self, event: tk.Event) -> None:
        if self.drag_start is None or self.state is None:
            return
        end = (float(event.x), float(event.y))
        try:
            self.state.add_rectangle(self.drag_start, end)
        except ValueError:
            pass
        finally:
            self.drag_start = None
            self.preview_rect = None
            self._render()

    def _render(self) -> None:
        self.canvas.delete("all")
        if self.state is None or self.source_image is None:
            self.canvas.create_text(
                self._canvas_size()[0] / 2,
                self._canvas_size()[1] / 2,
                text="选择一张 DWS 现场图片开始 ROI 标定",
                fill="#a8b7c9",
                font=("Microsoft YaHei UI", 14),
            )
            return

        transform = self.state.transform
        rendered_width, rendered_height = transform.rendered_size
        image = self.source_image.resize(
            (max(1, round(rendered_width)), max(1, round(rendered_height))),
            Image.Resampling.LANCZOS,
        )
        self.photo_image = ImageTk.PhotoImage(image)
        offset_x, offset_y = transform.offset
        self.canvas.create_image(
            offset_x,
            offset_y,
            image=self.photo_image,
            anchor="nw",
        )
        self._draw_rect(self.state.detect_rect, "#ffb000", 3)
        self._draw_polygon(self.state.belt_polygon)
        for rect in self.state.ignore_rects:
            self._draw_rect(rect, "#ff5c5c", 2)

    def _draw_rect(
        self,
        rect: tuple[int, int, int, int] | None,
        color: str,
        width: int,
    ) -> None:
        if rect is None or self.state is None:
            return
        x1, y1 = self.state.transform.image_to_canvas((rect[0], rect[1]))
        x2, y2 = self.state.transform.image_to_canvas((rect[2], rect[3]))
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=width)

    def _draw_polygon(self, points: list[tuple[int, int]]) -> None:
        if not points or self.state is None:
            return
        canvas_points = [
            self.state.transform.image_to_canvas(point)
            for point in points
        ]
        flat = [coordinate for point in canvas_points for coordinate in point]
        if len(points) >= 2:
            self.canvas.create_line(
                *flat,
                fill="#00e5ff",
                width=3,
                joinstyle="round",
            )
        if len(points) >= 3:
            self.canvas.create_line(
                *canvas_points[-1],
                *canvas_points[0],
                fill="#00e5ff",
                width=3,
            )
        for index, (x, y) in enumerate(canvas_points, start=1):
            self.canvas.create_oval(
                x - 5,
                y - 5,
                x + 5,
                y + 5,
                fill="#00e5ff",
                outline="#062b35",
            )
            self.canvas.create_text(
                x + 10,
                y - 10,
                text=str(index),
                fill="white",
                font=("Microsoft YaHei UI", 9, "bold"),
            )
