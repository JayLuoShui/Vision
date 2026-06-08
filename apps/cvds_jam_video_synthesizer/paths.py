from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "CVDS_Jam_Video_Synthesizer"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_projects_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    return Path(local_app_data) / "CVDS" / APP_DIR_NAME / "projects"


def runtime_ffmpeg_path() -> Path:
    return app_dir() / "runtime" / "ffmpeg.exe"
