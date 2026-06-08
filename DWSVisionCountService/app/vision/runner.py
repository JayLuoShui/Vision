"""兼容脚本调用的视觉 runner。"""

from __future__ import annotations

from datetime import datetime

from app.config import Config
from app.schemas import CountResult, ImageMeta
from app.vision.counter import ParcelCounter


class VisionRunner:
    """旧接口薄封装，内部复用 ParcelCounter。"""

    def __init__(self, config: Config):
        self.config = config
        self.counter = ParcelCounter(config)
        self.counter.load()

    def count_from_buffer(
        self,
        image_bytes: bytes,
        task_id: str | None = None,
        image_encoding: str | None = None,
    ) -> CountResult:
        meta = ImageMeta(
            task_id=task_id or datetime.now().strftime("%Y%m%d%H%M%S%f"),
            image_encoding=image_encoding or self.config.service.default_image_encoding,
            image_len=len(image_bytes),
        )
        return self.counter.count_bytes(meta, image_bytes)

    def get_backend_info(self) -> dict:
        health = self.counter.health()
        return {
            "type": health["backend"],
            "model_path": health["model_path"],
            "device": health["device"],
            "ready": health["model_loaded"],
        }

    def close(self) -> None:
        return None
