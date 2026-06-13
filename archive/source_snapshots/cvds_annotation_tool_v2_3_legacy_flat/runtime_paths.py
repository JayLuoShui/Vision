from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    app_name: str = "AnnotationTool"

    @property
    def frozen(self) -> bool:
        return bool(getattr(sys, "frozen", False))

    @property
    def install_dir(self) -> Path:
        if self.frozen:
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[1]

    @property
    def user_data_dir(self) -> Path:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            base = Path(local_appdata)
        else:
            base = Path.home() / "AppData" / "Local"
        return base / "CVDS" / self.app_name

    @property
    def resources_dir(self) -> Path:
        return self.install_dir / "resources"

    @property
    def default_weights_dir(self) -> Path:
        return self.install_dir / "weights"

    @property
    def default_weights_path(self) -> Path:
        candidates = sorted(self.default_weights_dir.glob("*.pt")) if self.default_weights_dir.exists() else []
        return candidates[0] if candidates else self.default_weights_dir / "cvds_yolo26n_package_best.pt"

    @property
    def default_output_dir(self) -> Path:
        return self.user_data_dir / "datasets" / "cvds_annotation_yolo"

    @property
    def default_image_dir(self) -> Path:
        return self.user_data_dir / "images"

    @property
    def default_video_dir(self) -> Path:
        return self.user_data_dir / "videos"

    @property
    def logs_dir(self) -> Path:
        return self.user_data_dir / "logs"

    @property
    def backups_dir(self) -> Path:
        return self.user_data_dir / "backups"

    @property
    def cache_dir(self) -> Path:
        return self.user_data_dir / "cache"

    @property
    def trash_dir(self) -> Path:
        return self.default_output_dir / ".trash"

    @property
    def reports_dir(self) -> Path:
        return self.default_output_dir / "reports"

    def ensure_user_dirs(self) -> None:
        for path in [
            self.user_data_dir,
            self.default_output_dir,
            self.logs_dir,
            self.backups_dir,
            self.cache_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> dict[str, Path | bool]:
        return {
            "frozen": self.frozen,
            "install_dir": self.install_dir,
            "user_data_dir": self.user_data_dir,
            "resources_dir": self.resources_dir,
            "default_weights_dir": self.default_weights_dir,
            "default_weights_path": self.default_weights_path,
            "default_output_dir": self.default_output_dir,
            "default_image_dir": self.default_image_dir,
            "default_video_dir": self.default_video_dir,
            "logs_dir": self.logs_dir,
            "backups_dir": self.backups_dir,
            "cache_dir": self.cache_dir,
            "trash_dir": self.trash_dir,
            "reports_dir": self.reports_dir,
        }


def get_runtime_paths() -> RuntimePaths:
    return RuntimePaths()
