# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathSelector(QWidget):
    def __init__(self, button_text: str = "选择") -> None:
        super().__init__()
        self.edit = QLineEdit()
        self.button = QPushButton(button_text)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, value: str) -> None:
        self.edit.setText(value)
