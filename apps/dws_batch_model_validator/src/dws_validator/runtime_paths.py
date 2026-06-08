# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_VENDOR = "CVDS"
APP_NAME = "DWSBatchModelValidator"


def _local_app_data() -> Path:
    value = os.environ.get("LOCALAPPDATA")
    if value:
        return Path(value)
    return Path.home() / "AppData" / "Local"


@dataclass(frozen=True)
class RuntimePaths:
    app_name: str = APP_NAME
    vendor: str = APP_VENDOR

    @property
    def frozen(self) -> bool:
        return bool(getattr(sys, "frozen", False))

    @property
    def app_dir(self) -> Path:
        if self.frozen:
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]

    @property
    def resource_dir(self) -> Path:
        if self.frozen:
            return Path(getattr(sys, "_MEIPASS", self.app_dir)).resolve()
        return self.app_dir

    @property
    def user_data_dir(self) -> Path:
        return _local_app_data() / self.vendor / self.app_name

    @property
    def default_output_dir(self) -> Path:
        return self.user_data_dir / "outputs" / "runs"

    @property
    def default_config_dir(self) -> Path:
        return self.user_data_dir / "config"

    @property
    def default_log_dir(self) -> Path:
        return self.user_data_dir / "logs"

    @property
    def default_model_dir(self) -> Path:
        return self.resource_dir / "models"

    @property
    def bundled_config_path(self) -> Path:
        return self.resource_dir / "configs" / "default.yaml"

    def ensure_user_dirs(self) -> None:
        for path in [self.user_data_dir, self.default_output_dir, self.default_config_dir, self.default_log_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def resolve_app_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.resource_dir / path).resolve()

    def resolve_cwd_path(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (Path.cwd() / path).resolve()

    def is_writable_directory(self, path: str | Path) -> bool:
        target = Path(path)
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".write_probe.tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False


def get_runtime_paths() -> RuntimePaths:
    return RuntimePaths()
