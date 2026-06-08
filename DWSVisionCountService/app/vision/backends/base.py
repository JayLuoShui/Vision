"""推理后端抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from app.schemas import Detection


class BaseVisionBackend(ABC):
    """所有视觉推理后端必须实现的接口。"""

    @abstractmethod
    def load(self) -> None:
        """加载模型。"""

    @abstractmethod
    def predict(self, image_bgr: np.ndarray) -> list[Detection]:
        """输入 1024x1024 BGR 图像，输出统一 Detection。"""

    @abstractmethod
    def warmup(self) -> None:
        """预热模型。"""

    @abstractmethod
    def is_loaded(self) -> bool:
        """返回模型是否已加载。"""
