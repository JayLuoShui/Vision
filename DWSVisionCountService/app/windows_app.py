"""DWS 视觉计数 Windows 桌面程序。"""

from __future__ import annotations

import asyncio
import argparse
import os
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from loguru import logger
from PIL import Image, ImageTk

from app.config import Config
from app.logger import setup_logging
from app.roi_canvas import ROIEditorPanel
from app.schemas import CountResult
from app.tcp_server import TCPServer
from app.utils.turbojpeg_decoder import verify_turbojpeg_available
from app.vision.counter import ParcelCounter
from app.windows_settings import IgnoreRectDraft, SettingsDraft, build_config


@dataclass(frozen=True)
class ServiceSnapshot:
    state: str = "stopped"
    request_count: int = 0
    error_count: int = 0
    last_task_id: str = "-"
    last_parcel_count: int = 0
    last_processing_time_ms: int = 0
    last_error: str = ""


class ServiceController:
    """在独立线程中运行 asyncio TCP 服务。"""

    def __init__(self, config: Config, server_factory=TCPServer):
        self.config = config
        self.server_factory = server_factory
        self._lock = threading.Lock()
        self._snapshot = ServiceSnapshot()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None

    def snapshot(self) -> ServiceSnapshot:
        with self._lock:
            return self._snapshot

    def start(self) -> None:
        with self._lock:
            if self._snapshot.state in {"starting", "running", "stopping"}:
                return
            self._snapshot = ServiceSnapshot(
                state="starting",
                request_count=self._snapshot.request_count,
                error_count=self._snapshot.error_count,
            )
        self._thread = threading.Thread(
            target=self._thread_main,
            name="dws-tcp-service",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        with self._lock:
            if self._snapshot.state in {"stopped", "stopping"}:
                return
            self._snapshot = self._replace_snapshot(state="stopping")
            loop = self._loop
            server = self._server
        if loop is not None and server is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(server.stop(), loop)
            future.result(timeout=timeout)
            loop.call_soon_threadsafe(loop.stop)
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def restart(self, config: Config, timeout: float = 30.0) -> None:
        self.stop(timeout=timeout)
        with self._lock:
            self.config = config
            self._thread = None
            self._snapshot = ServiceSnapshot(
                request_count=self._snapshot.request_count,
                error_count=self._snapshot.error_count,
            )
        self.start()

    def record_result(self, result: CountResult | dict[str, Any]) -> None:
        data = result.to_dict() if isinstance(result, CountResult) else result
        with self._lock:
            code = int(data.get("code", 5000))
            self._snapshot = ServiceSnapshot(
                state=self._snapshot.state,
                request_count=self._snapshot.request_count + 1,
                error_count=self._snapshot.error_count + int(code != 0),
                last_task_id=str(data.get("task_id", "-")),
                last_parcel_count=int(data.get("parcel_count", 0)),
                last_processing_time_ms=int(data.get("processing_time_ms", 0)),
                last_error="" if code == 0 else str(data.get("message", "unknown error")),
            )

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
        try:
            server = self.server_factory(
                self.config,
                result_callback=self.record_result,
            )
            with self._lock:
                self._server = server
            loop.run_until_complete(server.start())
            with self._lock:
                self._snapshot = self._replace_snapshot(state="running", last_error="")
            loop.run_forever()
        except Exception as exc:
            logger.exception("Windows service controller failed: {}", exc)
            with self._lock:
                self._snapshot = self._replace_snapshot(
                    state="error",
                    last_error=str(exc),
                )
        finally:
            loop.close()
            with self._lock:
                self._loop = None
                self._server = None
                if self._snapshot.state != "error":
                    self._snapshot = self._replace_snapshot(state="stopped")

    def _replace_snapshot(self, **changes) -> ServiceSnapshot:
        values = self._snapshot.__dict__ | changes
        return ServiceSnapshot(**values)


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def window_title(config: Config) -> str:
    return f"DWS 视觉计数服务 v{config.service.version}"


def bundled_resource(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", application_root()))
    return base.joinpath(*parts)


def run_diagnostics(app_root: Path, counter_factory=ParcelCounter) -> int:
    """验证发布目录、原生解码器和模型是否可用。"""
    config_path = app_root / "config" / "config.yaml"
    if not config_path.exists():
        config_path = app_root / "config.yaml"
    try:
        config = Config.from_yaml(config_path)
        if counter_factory is ParcelCounter:
            verify_turbojpeg_available()
        counter = counter_factory(config)
        counter.load()
        return 0 if counter.backend.is_loaded() else 1
    except Exception as exc:
        logger.exception("diagnostics failed: {}", exc)
        return 1


class DWSWindowsApp:
    """Windows 工业控制台：服务状态、参数设置和 ROI 标定。"""

    STATE_TEXT = {
        "stopped": "已停止",
        "starting": "模型加载中",
        "running": "服务运行中",
        "stopping": "正在停止",
        "error": "启动失败",
    }
    STATE_COLOR = {
        "stopped": "#78889b",
        "starting": "#ffb000",
        "running": "#22c987",
        "stopping": "#ffb000",
        "error": "#ff5c5c",
    }

    def __init__(
        self,
        root: tk.Tk,
        config: Config,
        app_root: Path,
        config_path: Path,
        auto_start: bool = True,
    ):
        self.root = root
        self.config = config
        self.app_root = app_root
        self.config_path = config_path
        self.controller = ServiceController(config)
        self._stopping = False
        self._saving = False
        self.logo_photo: ImageTk.PhotoImage | None = None
        self.window_icon: tk.PhotoImage | None = None
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        if auto_start:
            self.root.after(200, self.controller.start)
        self.root.after(250, self._refresh)

    def _build_ui(self) -> None:
        self.root.title(window_title(self.config))
        self.root.geometry("1360x820")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#0d1724")
        self._set_window_icon()

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background="#f4f7fa")
        style.configure("TLabel", background="#f4f7fa", foreground="#1c2a3a")
        style.configure("TNotebook", background="#f4f7fa", borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            font=("Microsoft YaHei UI", 11, "bold"),
            padding=(22, 11),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff"), ("!selected", "#dfe7ef")],
            foreground=[("selected", "#1677ff"), ("!selected", "#516275")],
        )
        style.configure(
            "Primary.TButton",
            font=("Microsoft YaHei UI", 10, "bold"),
            padding=(18, 10),
            foreground="white",
            background="#1677ff",
        )
        style.map("Primary.TButton", background=[("active", "#075fda")])
        style.configure("TButton", padding=(14, 8))
        style.configure("Form.TLabelframe", background="#ffffff", padding=14)
        style.configure(
            "Form.TLabelframe.Label",
            background="#ffffff",
            foreground="#1c2a3a",
            font=("Microsoft YaHei UI", 11, "bold"),
        )

        shell = tk.Frame(self.root, bg="#0d1724")
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg="#0d1724", width=240)
        content = ttk.Frame(shell, padding=20)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        content.grid(row=0, column=1, sticky="nsew")
        self._build_sidebar(sidebar)
        self._build_content(content)

    def _set_window_icon(self) -> None:
        png_path = bundled_resource("app", "assets", "app_icon.png")
        ico_path = bundled_resource("app", "assets", "app_icon.ico")
        if png_path.is_file():
            self.window_icon = tk.PhotoImage(file=str(png_path))
            self.root.iconphoto(True, self.window_icon)
        if ico_path.is_file():
            self.root.iconbitmap(str(ico_path))

    def _build_sidebar(self, parent: tk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(4, weight=1)
        brand = tk.Frame(parent, bg="#0d1724")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        icon_path = bundled_resource("app", "assets", "app_icon.png")
        if icon_path.is_file():
            image = Image.open(icon_path).resize((68, 68), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(image)
            tk.Label(brand, image=self.logo_photo, bg="#0d1724").pack(anchor="w")
        tk.Label(
            brand,
            text="DWS VISION",
            bg="#0d1724",
            fg="#f7fbff",
            font=("Bahnschrift SemiBold", 17),
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            brand,
            text=f"视觉计数服务  v{self.config.service.version}",
            bg="#0d1724",
            fg="#8fa4ba",
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w")

        status = tk.Frame(parent, bg="#152338", padx=18, pady=16)
        status.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 10))
        top = tk.Frame(status, bg="#152338")
        top.pack(fill="x")
        self.status_dot = tk.Canvas(
            top,
            width=18,
            height=18,
            bg="#152338",
            highlightthickness=0,
        )
        self.status_dot.pack(side="left")
        self.status_dot_id = self.status_dot.create_oval(
            3,
            3,
            15,
            15,
            fill="#ffb000",
            outline="",
        )
        self.status_var = tk.StringVar(value="准备启动")
        tk.Label(
            top,
            textvariable=self.status_var,
            bg="#152338",
            fg="white",
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(side="left", padx=(8, 0))
        self.endpoint_var = tk.StringVar(
            value=f"{self.config.service.host}:{self.config.service.tcp_port}"
        )
        tk.Label(
            status,
            textvariable=self.endpoint_var,
            bg="#152338",
            fg="#8fa4ba",
            font=("Consolas", 11),
        ).pack(anchor="w", pady=(8, 0))

        metrics = tk.Frame(parent, bg="#0d1724")
        metrics.grid(row=3, column=0, sticky="ew", padx=16, pady=(10, 0))
        self.request_var = tk.StringVar(value="0")
        self.count_var = tk.StringVar(value="-")
        self.time_var = tk.StringVar(value="-")
        self.error_var = tk.StringVar(value="0")
        for index, (title, variable) in enumerate(
            [
                ("请求", self.request_var),
                ("包裹", self.count_var),
                ("耗时", self.time_var),
                ("错误", self.error_var),
            ]
        ):
            card = tk.Frame(metrics, bg="#152338", padx=12, pady=10)
            row, column = divmod(index, 2)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 5, 5 if column == 0 else 0),
                pady=(0, 6),
            )
            tk.Label(
                card,
                text=title,
                bg="#152338",
                fg="#8fa4ba",
                font=("Microsoft YaHei UI", 9),
            ).pack(anchor="w")
            tk.Label(
                card,
                textvariable=variable,
                bg="#152338",
                fg="white",
                font=("Bahnschrift SemiBold", 17),
            ).pack(anchor="w")
            metrics.columnconfigure(column, weight=1)

        latest = tk.Frame(parent, bg="#0d1724")
        latest.grid(
            row=4,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(10, 0),
        )
        tk.Label(
            latest,
            text="最近任务",
            bg="#0d1724",
            fg="#8fa4ba",
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")
        self.task_var = tk.StringVar(value="-")
        self.detail_var = tk.StringVar(value="等待 DWS 发送数据")
        tk.Label(
            latest,
            textvariable=self.task_var,
            bg="#0d1724",
            fg="white",
            font=("Consolas", 11, "bold"),
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            latest,
            textvariable=self.detail_var,
            bg="#0d1724",
            fg="#8fa4ba",
            justify="left",
            wraplength=250,
        ).pack(anchor="w", pady=(6, 0))

        actions = tk.Frame(parent, bg="#0d1724")
        actions.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.start_button = ttk.Button(
            actions,
            text="启动服务",
            command=self.controller.start,
        )
        self.start_button.pack(fill="x")
        self.stop_button = ttk.Button(
            actions,
            text="停止服务",
            command=self._stop_async,
        )
        self.stop_button.pack(fill="x", pady=(8, 0))
        ttk.Button(
            actions,
            text="打开程序目录",
            command=self._open_app_dir,
        ).pack(fill="x", pady=(8, 0))

    def _build_content(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="检测控制台",
            font=("Microsoft YaHei UI", 22, "bold"),
        ).pack(anchor="w")
        self.save_state_var = tk.StringVar(
            value="参数保存后会完整重启服务，当前请求不会使用混合配置"
        )
        ttk.Label(parent, textvariable=self.save_state_var).pack(
            anchor="w",
            pady=(4, 14),
        )
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)
        settings_tab = ttk.Frame(self.notebook)
        roi_tab = ttk.Frame(self.notebook)
        self.notebook.add(settings_tab, text="运行设置")
        self.notebook.add(roi_tab, text="ROI 标定")
        settings_body = self._scrollable_body(settings_tab)
        self._build_settings_tab(settings_body)

        roi_tab.rowconfigure(0, weight=1)
        roi_tab.columnconfigure(0, weight=1)
        self.roi_panel = ROIEditorPanel(roi_tab, self.config)
        self.roi_panel.grid(row=0, column=0, sticky="nsew")
        roi_actions = ttk.Frame(roi_tab, padding=(16, 8, 16, 16))
        roi_actions.grid(row=1, column=0, sticky="ew")
        ttk.Label(
            roi_actions,
            text="ROI 与运行参数作为同一份配置保存",
        ).pack(side="left")
        self.roi_save_button = ttk.Button(
            roi_actions,
            text="保存全部并重启服务",
            style="Primary.TButton",
            command=self._save_settings,
        )
        self.roi_save_button.pack(side="right")

    @staticmethod
    def _scrollable_body(parent: ttk.Frame) -> ttk.Frame:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        canvas = tk.Canvas(
            parent,
            bg="#f4f7fa",
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        body = ttk.Frame(canvas, padding=18)
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window, width=event.width),
        )
        return body

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        runtime = ttk.LabelFrame(
            parent,
            text="网络与推理",
            style="Form.TLabelframe",
        )
        runtime.grid(row=0, column=0, sticky="ew")
        runtime.columnconfigure(1, weight=1)
        self.tcp_port_var = tk.StringVar(value=str(self.config.service.tcp_port))
        self.model_path_var = tk.StringVar(value=self.config.model.model_path)
        self.confidence_var = tk.StringVar(
            value=f"{self.config.model.confidence_threshold:.2f}"
        )
        self.iou_var = tk.StringVar(value=f"{self.config.model.iou_threshold:.2f}")
        self.threads_var = tk.StringVar(
            value=str(self.config.model.inference_num_threads)
        )
        self.reduce_var = tk.StringVar(
            value=str(self.config.service.decode_reduce_factor)
        )
        self.debug_var = tk.BooleanVar(value=self.config.debug.save_debug_image)

        self._form_entry(runtime, 0, "TCP 端口", self.tcp_port_var)
        ttk.Label(runtime, text="模型目录").grid(
            row=1,
            column=0,
            sticky="w",
            pady=7,
        )
        model_row = ttk.Frame(runtime)
        model_row.grid(row=1, column=1, sticky="ew", padx=(18, 0), pady=7)
        model_row.columnconfigure(0, weight=1)
        ttk.Entry(model_row, textvariable=self.model_path_var).grid(
            row=0,
            column=0,
            sticky="ew",
        )
        ttk.Button(model_row, text="选择", command=self._browse_model).grid(
            row=0,
            column=1,
            padx=(8, 0),
        )
        self._form_entry(runtime, 2, "置信度", self.confidence_var)
        self._form_entry(runtime, 3, "IoU 阈值", self.iou_var)
        self._form_entry(runtime, 4, "推理线程", self.threads_var)

        ttk.Label(runtime, text="JPEG reduce").grid(
            row=5,
            column=0,
            sticky="w",
            pady=7,
        )
        reduce_box = ttk.Combobox(
            runtime,
            textvariable=self.reduce_var,
            values=["1", "2", "4", "8"],
            state="readonly",
            width=12,
        )
        reduce_box.grid(row=5, column=1, sticky="w", padx=(18, 0), pady=7)
        ttk.Label(
            runtime,
            text="1 为已验证生产质量；2/4/8 修改后必须重新做现场质量验证",
            foreground="#a25800",
        ).grid(row=6, column=1, sticky="w", padx=(18, 0), pady=(0, 8))
        ttk.Checkbutton(
            runtime,
            text="保存检测调试图",
            variable=self.debug_var,
        ).grid(row=7, column=1, sticky="w", padx=(18, 0), pady=7)

        current = ttk.LabelFrame(
            parent,
            text="当前配置",
            style="Form.TLabelframe",
        )
        current.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        current.columnconfigure(1, weight=1)
        self.model_var = tk.StringVar(value=self.config.model.model_path)
        ttk.Label(current, text="监听地址").grid(row=0, column=0, sticky="nw")
        ttk.Label(current, textvariable=self.endpoint_var).grid(
            row=0,
            column=1,
            sticky="w",
            padx=(18, 0),
        )
        ttk.Label(current, text="正在使用模型").grid(
            row=1,
            column=0,
            sticky="nw",
            pady=(10, 0),
        )
        ttk.Label(
            current,
            textvariable=self.model_var,
            wraplength=650,
        ).grid(row=1, column=1, sticky="w", padx=(18, 0), pady=(10, 0))

        footer = ttk.Frame(parent)
        footer.grid(row=2, column=0, sticky="ew", pady=(18, 0))
        ttk.Label(
            footer,
            text="所有字段校验通过后才会写入 config/config.yaml",
        ).pack(side="left")
        self.settings_save_button = ttk.Button(
            footer,
            text="保存全部并重启服务",
            style="Primary.TButton",
            command=self._save_settings,
        )
        self.settings_save_button.pack(side="right")

    @staticmethod
    def _form_entry(
        parent: ttk.LabelFrame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=7)
        ttk.Entry(parent, textvariable=variable, width=24).grid(
            row=row,
            column=1,
            sticky="w",
            padx=(18, 0),
            pady=7,
        )

    def _browse_model(self) -> None:
        path = filedialog.askdirectory(
            title="选择 OpenVINO 模型目录",
            initialdir=str(self.app_root),
        )
        if path:
            self.model_path_var.set(path)

    def _collect_settings(self) -> SettingsDraft:
        width, height, detect, polygon, ignore_rects = self.roi_panel.region_values()
        existing_names = [region.name for region in self.config.ignore_regions]
        ignores = tuple(
            IgnoreRectDraft(
                name=(
                    existing_names[index]
                    if index < len(existing_names) and existing_names[index]
                    else f"ignore_{index + 1}"
                ),
                x1=rect[0],
                y1=rect[1],
                x2=rect[2],
                y2=rect[3],
            )
            for index, rect in enumerate(ignore_rects)
        )
        return SettingsDraft(
            tcp_port=int(self.tcp_port_var.get()),
            model_path=self.model_path_var.get().strip(),
            confidence_threshold=float(self.confidence_var.get()),
            iou_threshold=float(self.iou_var.get()),
            inference_num_threads=int(self.threads_var.get()),
            decode_reduce_factor=int(self.reduce_var.get()),
            save_debug_image=bool(self.debug_var.get()),
            image_width=width,
            image_height=height,
            detect_roi_rect=detect,
            belt_polygon=polygon,
            ignore_regions=ignores,
        )

    def _save_settings(self) -> None:
        if self._saving:
            return
        try:
            draft = self._collect_settings()
            updated = build_config(self.config, draft, self.app_root)
            updated.to_yaml(self.config_path)
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror("配置保存失败", str(exc))
            return
        self._saving = True
        self._set_save_buttons("disabled")
        self.save_state_var.set("配置已写入，正在重新加载模型并启动服务...")
        threading.Thread(
            target=self._restart_after_save,
            args=(updated,),
            daemon=True,
        ).start()

    def _restart_after_save(self, updated: Config) -> None:
        error: Exception | None = None
        try:
            self.controller.restart(updated)
        except Exception as exc:
            logger.exception("service restart after config save failed: {}", exc)
            error = exc
        self.root.after(0, self._finish_save, updated, error)

    def _finish_save(self, updated: Config, error: Exception | None) -> None:
        self._saving = False
        self._set_save_buttons("normal")
        if error is not None:
            self.save_state_var.set("配置已保存，但服务重启失败")
            messagebox.showerror("服务重启失败", str(error))
            return
        self.config = updated
        self.roi_panel.apply_config(updated)
        self.endpoint_var.set(
            f"{updated.service.host}:{updated.service.tcp_port}"
        )
        self.model_var.set(updated.model.model_path)
        self.save_state_var.set("配置保存成功，服务正在使用新配置启动")

    def _set_save_buttons(self, state: str) -> None:
        self.settings_save_button.configure(state=state)
        self.roi_save_button.configure(state=state)

    def _refresh(self) -> None:
        snapshot = self.controller.snapshot()
        self.status_var.set(self.STATE_TEXT.get(snapshot.state, snapshot.state))
        self.status_dot.itemconfigure(
            self.status_dot_id,
            fill=self.STATE_COLOR.get(snapshot.state, "#78889b"),
        )
        self.request_var.set(str(snapshot.request_count))
        self.count_var.set(
            str(snapshot.last_parcel_count) if snapshot.request_count else "-"
        )
        self.time_var.set(
            f"{snapshot.last_processing_time_ms}ms"
            if snapshot.request_count
            else "-"
        )
        self.error_var.set(str(snapshot.error_count))
        self.task_var.set(snapshot.last_task_id)
        self.detail_var.set(snapshot.last_error or "检测结果已通过 TCP 返回 DWS")
        self.start_button.configure(
            state=(
                "disabled"
                if snapshot.state in {"starting", "running", "stopping"}
                else "normal"
            )
        )
        self.stop_button.configure(
            state=(
                "normal"
                if snapshot.state in {"starting", "running"}
                else "disabled"
            )
        )
        if not self._stopping:
            self.root.after(250, self._refresh)

    def _stop_async(self) -> None:
        threading.Thread(target=self.controller.stop, daemon=True).start()

    def _open_app_dir(self) -> None:
        subprocess.Popen(["explorer.exe", str(self.app_root)])

    def _on_close(self) -> None:
        if not messagebox.askokcancel(
            "退出",
            "退出软件将停止 DWS 检测服务，确定退出吗？",
        ):
            return
        self._stopping = True
        try:
            self.controller.stop(timeout=10)
        finally:
            self.root.destroy()


def main() -> None:
    root_dir = application_root()
    os.chdir(root_dir)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--diagnose", action="store_true")
    args, _ = parser.parse_known_args()
    if args.diagnose:
        raise SystemExit(run_diagnostics(root_dir))
    config_path = root_dir / "config" / "config.yaml"
    config = Config.from_yaml(config_path)
    setup_logging(config)
    root = tk.Tk()
    DWSWindowsApp(root, config, root_dir, config_path)
    root.mainloop()


if __name__ == "__main__":
    main()
