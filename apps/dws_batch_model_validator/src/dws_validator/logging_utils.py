# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from .runtime_paths import RuntimePaths


class CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None] | None) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        if self.callback is None:
            return
        try:
            self.callback(self.format(record))
        except Exception:
            self.handleError(record)


def create_run_logger(name: str = "dws_validator", log_cb: Callable[[str], None] | None = None) -> tuple[logging.Logger, Path]:
    paths = RuntimePaths()
    paths.ensure_user_dirs()
    log_path = paths.default_log_dir / f"app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    callback_handler = CallbackLogHandler(log_cb)
    callback_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(callback_handler)
    return logger, log_path
