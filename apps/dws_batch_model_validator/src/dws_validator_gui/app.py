# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DWS 批量模型检测验证工具 GUI")
    parser.add_argument("--qapplication-test", action="store_true")
    parser.add_argument("--window-smoke-test", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    if args.qapplication_test:
        return 0
    window = MainWindow()
    if args.window_smoke_test:
        window.show()
        print("DWS GUI window ok")
        return 0
    window.show()
    return int(app.exec())
