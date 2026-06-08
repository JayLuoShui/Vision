# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from dws_validator.config import RuntimeConfig
from dws_validator.logging_utils import create_run_logger
from dws_validator.runner import run_batch


class BatchValidationWorker(QObject):
    progress = Signal(int, int, str)
    rowReady = Signal(dict)
    log = Signal(str)
    previewReady = Signal(str)
    summaryReady = Signal(dict)
    failed = Signal(str)
    finished = Signal()
    cancelled = Signal()

    def __init__(self, cfg: RuntimeConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _progress(self, index: int, total: int, image_name: str, row: dict[str, Any]) -> None:
        self.progress.emit(index, total, image_name)
        self.rowReady.emit(row)
        preview = str(row.get("_preview_path") or "")
        if preview:
            self.previewReady.emit(preview)

    def _log(self, message: str) -> None:
        self.log.emit(message)

    @Slot()
    def run(self) -> None:
        logger, log_path = create_run_logger(log_cb=self._log)
        try:
            logger.info("日志文件：%s", log_path)
            summary = run_batch(
                self.cfg,
                progress_cb=self._progress,
                log_cb=logger.info,
                cancel_cb=lambda: self._cancelled,
            )
            self.summaryReady.emit(summary)
            if self._cancelled or summary.get("cancelled"):
                self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            logger.error(tb)
            self.failed.emit(f"{exc}\n{tb}")
        finally:
            self.finished.emit()
