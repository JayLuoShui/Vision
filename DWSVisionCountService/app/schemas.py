"""Pydantic schemas for DWSVisionCountService.

Defines request/response structures used across the TCP and HTTP servers.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field, ConfigDict


class ImageMeta(BaseModel):
    """Metadata header parsed from the DWS/WDS request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    timestamp: Optional[str] = None
    barcode: Optional[str] = None
    image_encoding: str = "encoded"
    image_len: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None
    pixel_format: Optional[str] = None
    dws_meta: Optional[dict[str, Any]] = None


class DecodedImage(BaseModel):
    """Result of decoding raw bytes into a BGR numpy array."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    image_bgr: np.ndarray
    width: int
    height: int
    source_encoding: str
    original_width: Optional[int] = None
    original_height: Optional[int] = None
    decode_scale_x: float = 1.0
    decode_scale_y: float = 1.0


class Detection(BaseModel):
    """Single detection from the model backend."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    class_id: int
    class_name: str
    score: float
    box_model: list[float] = Field(default_factory=list)  # [x1,y1,x2,y2] in model coords
    mask_model: Optional[np.ndarray] = None
    mask_area_model: Optional[float] = None


class CountObject(BaseModel):
    """Post-processed object that passed all filters."""

    class_id: int
    class_name: str
    score: float
    box: list[float] = Field(default_factory=list)  # [x1,y1,x2,y2] in raw image
    center: list[float] = Field(default_factory=list)  # [cx, cy] in raw image
    box_area: float = 0.0
    mask_area: Optional[float] = None


class CountResult(BaseModel):
    """Final counting result for a single task."""

    task_id: str
    code: int  # 0=ok, >0=error code
    message: str
    parcel_count: int = 0
    confidence: float = 0.0
    processing_time_ms: int = 0
    decode_time_ms: int = 0
    preprocess_time_ms: int = 0
    inference_time_ms: int = 0
    postprocess_time_ms: int = 0
    model: str = ""
    image_width: int = 0
    image_height: int = 0
    objects: list[CountObject] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serialisable dict (numpy types to Python native)."""
        result = self.model_dump(exclude_unset=True)
        # Convert numpy types to native python for JSON serialisation
        for obj in result.get("objects", []):
            obj["box"] = [float(v) for v in obj.get("box", [])]
            obj["center"] = [float(v) for v in obj.get("center", [])]
            obj["score"] = float(obj.get("score", 0.0))
            if obj.get("mask_area") is not None:
                obj["mask_area"] = float(obj["mask_area"])
            obj["box_area"] = float(obj.get("box_area", 0.0))
        result["objects"] = result.get("objects", [])
        result["confidence"] = float(result.get("confidence", 0.0))
        return result
