from __future__ import annotations

from . import APP_VERSION

APP_NAME = "CVDS AI 辅助 YOLO 标注工具 v2.3"
SETTINGS_ORG = "CVDS"
SETTINGS_APP = "AnnotationToolV23"
DEFECT_META_VERSION = 3
DEFECT_TYPES = ("hole", "crack", "tear", "dent", "contamination", "other")
DEFECT_SEVERITIES = ("low", "medium", "high")
DEFECT_KINDS = ("polygon", "box", "point")

__all__ = [
    "APP_VERSION",
    "APP_NAME",
    "SETTINGS_ORG",
    "SETTINGS_APP",
    "DEFECT_META_VERSION",
    "DEFECT_TYPES",
    "DEFECT_SEVERITIES",
    "DEFECT_KINDS",
]
