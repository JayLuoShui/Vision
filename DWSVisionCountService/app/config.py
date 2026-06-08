"""Configuration loader for DWSVisionCountService.

Reads config.yaml and exposes a hierarchical Config object
with type-safe properties and sensible defaults.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import sys

import yaml
from loguru import logger


@dataclass
class CameraConfig:
    raw_width: int = 4024
    raw_height: int = 3036


@dataclass
class ServiceConfig:
    name: str = "DWSVisionCountService"
    version: str = "1.1.0"
    host: str = "0.0.0.0"
    http_port: int = 8080
    tcp_port: int = 9100
    request_timeout_ms: int = 3000
    max_image_bytes: int = 20_000_000
    default_image_encoding: str = "encoded"
    decode_reduce_factor: int = 1


@dataclass
class ModelConfig:
    backend: str = "ultralytics_openvino"
    model_path: str = "models/best_openvino_model"
    device: str = "CPU"
    imgsz: int = 1024
    batch: int = 1
    performance_hint: str = "LATENCY"
    inference_num_threads: int = 4
    confidence_threshold: float = 0.40
    iou_threshold: float = 0.55
    class_names: dict[str, str] = field(default_factory=lambda: {"0": "parcel"})
    target_class_name: str = "parcel"


@dataclass
class PreprocessConfig:
    mode: str = "roi_polygon_letterbox"
    infer_imgsz: int = 1024
    keep_ratio: bool = True
    normalize: bool = True
    mask_outside_polygon: bool = True
    mask_ignore_regions: bool = True
    tile_overlap_ratio: float = 0.10


@dataclass
class DetectROIRect:
    x1: int = 355
    y1: int = 0
    x2: int = 3540
    y2: int = 2595


@dataclass
class IgnoreRegion:
    name: str = ""
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0


@dataclass
class PostprocessConfig:
    count_by: str = "instance_mask"
    min_box_area_raw: int = 3000
    min_mask_area_raw: int = 2500
    duplicate_iou_threshold: float = 0.70
    duplicate_mask_iou_threshold: float = 0.70
    duplicate_mask_overlap_threshold: float = 0.10
    require_center_in_belt_polygon: bool = True
    edge_ignore_enabled: bool = False


@dataclass
class DebugConfig:
    save_debug_image: bool = True
    save_failed_image: bool = True
    save_input_image: bool = False
    debug_dir: str = "debug/images"
    failed_dir: str = "cache/failed"
    max_keep_days: int = 14


@dataclass
class LoggingConfig:
    log_dir: str = "logs"
    level: str = "INFO"
    rotation: str = "00:00"
    retention: str = "14 days"


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    service: ServiceConfig = field(default_factory=ServiceConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)
    detect_roi_rect: DetectROIRect = field(default_factory=DetectROIRect)
    belt_polygon: list[list[int]] = field(
        default_factory=lambda: [
            [826, 0],
            [3028, 0],
            [3430, 2487],
            [413, 2487],
        ]
    )
    ignore_regions: list[IgnoreRegion] = field(default_factory=list)
    postprocess: PostprocessConfig = field(default_factory=PostprocessConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def to_yaml(self, path: str | Path) -> None:
        """将完整配置以 UTF-8 编码保存到 YAML 文件。"""
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(asdict(self), f, allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML config file.

        Returns:
            Fully populated Config instance.
        """
        path = Path(path)
        if not path.exists():
            logger.warning("Config file not found at {}, using defaults.", path)
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        cfg = cls()

        if "camera" in data:
            d = data["camera"]
            cfg.camera = CameraConfig(
                raw_width=int(d.get("raw_width", cfg.camera.raw_width)),
                raw_height=int(d.get("raw_height", cfg.camera.raw_height)),
            )

        if "service" in data:
            d = data["service"]
            cfg.service = ServiceConfig(
                name=str(d.get("name", cfg.service.name)),
                version=str(d.get("version", cfg.service.version)),
                host=str(d.get("host", cfg.service.host)),
                http_port=int(d.get("http_port", cfg.service.http_port)),
                tcp_port=int(d.get("tcp_port", cfg.service.tcp_port)),
                request_timeout_ms=int(
                    d.get("request_timeout_ms", cfg.service.request_timeout_ms)
                ),
                max_image_bytes=int(
                    d.get("max_image_bytes", cfg.service.max_image_bytes)
                ),
                default_image_encoding=str(
                    d.get("default_image_encoding", cfg.service.default_image_encoding)
                ),
                decode_reduce_factor=int(
                    d.get("decode_reduce_factor", cfg.service.decode_reduce_factor)
                ),
            )

        if "model" in data:
            d = data["model"]
            cfg.model = ModelConfig(
                backend=str(d.get("backend", cfg.model.backend)),
                model_path=str(d.get("model_path", cfg.model.model_path)),
                device=str(d.get("device", cfg.model.device)),
                imgsz=int(d.get("imgsz", cfg.model.imgsz)),
                batch=int(d.get("batch", cfg.model.batch)),
                performance_hint=str(
                    d.get("performance_hint", cfg.model.performance_hint)
                ),
                inference_num_threads=int(
                    d.get("inference_num_threads", cfg.model.inference_num_threads)
                ),
                confidence_threshold=float(
                    d.get("confidence_threshold", cfg.model.confidence_threshold)
                ),
                iou_threshold=float(d.get("iou_threshold", cfg.model.iou_threshold)),
                class_names={
                    str(k): str(v)
                    for k, v in d.get("class_names", {}).items()
                },
                target_class_name=str(
                    d.get("target_class_name", cfg.model.target_class_name)
                ),
            )

        if "preprocess" in data:
            d = data["preprocess"]
            cfg.preprocess = PreprocessConfig(
                mode=str(d.get("mode", cfg.preprocess.mode)),
                infer_imgsz=int(d.get("infer_imgsz", cfg.preprocess.infer_imgsz)),
                keep_ratio=bool(d.get("keep_ratio", cfg.preprocess.keep_ratio)),
                normalize=bool(d.get("normalize", cfg.preprocess.normalize)),
                mask_outside_polygon=bool(
                    d.get("mask_outside_polygon", cfg.preprocess.mask_outside_polygon)
                ),
                mask_ignore_regions=bool(
                    d.get("mask_ignore_regions", cfg.preprocess.mask_ignore_regions)
                ),
                tile_overlap_ratio=float(
                    d.get("tile_overlap_ratio", cfg.preprocess.tile_overlap_ratio)
                ),
            )

        if "detect_roi_rect" in data:
            d = data["detect_roi_rect"]
            cfg.detect_roi_rect = DetectROIRect(
                x1=int(d.get("x1", cfg.detect_roi_rect.x1)),
                y1=int(d.get("y1", cfg.detect_roi_rect.y1)),
                x2=int(d.get("x2", cfg.detect_roi_rect.x2)),
                y2=int(d.get("y2", cfg.detect_roi_rect.y2)),
            )

        if "belt_polygon" in data:
            raw = data["belt_polygon"]
            cfg.belt_polygon = [
                [int(p[0]), int(p[1])] for p in raw
            ]

        if "ignore_regions" in data:
            raw = data["ignore_regions"]
            cfg.ignore_regions = [
                IgnoreRegion(
                    name=str(r.get("name", "")),
                    x1=int(r.get("x1", 0)),
                    y1=int(r.get("y1", 0)),
                    x2=int(r.get("x2", 0)),
                    y2=int(r.get("y2", 0)),
                )
                for r in raw
            ]

        if "postprocess" in data:
            d = data["postprocess"]
            cfg.postprocess = PostprocessConfig(
                count_by=str(d.get("count_by", cfg.postprocess.count_by)),
                min_box_area_raw=int(
                    d.get("min_box_area_raw", cfg.postprocess.min_box_area_raw)
                ),
                min_mask_area_raw=int(
                    d.get("min_mask_area_raw", cfg.postprocess.min_mask_area_raw)
                ),
                duplicate_iou_threshold=float(
                    d.get(
                        "duplicate_iou_threshold",
                        cfg.postprocess.duplicate_iou_threshold,
                    )
                ),
                duplicate_mask_iou_threshold=float(
                    d.get(
                        "duplicate_mask_iou_threshold",
                        cfg.postprocess.duplicate_mask_iou_threshold,
                    )
                ),
                duplicate_mask_overlap_threshold=float(
                    d.get(
                        "duplicate_mask_overlap_threshold",
                        cfg.postprocess.duplicate_mask_overlap_threshold,
                    )
                ),
                require_center_in_belt_polygon=bool(
                    d.get(
                        "require_center_in_belt_polygon",
                        cfg.postprocess.require_center_in_belt_polygon,
                    )
                ),
                edge_ignore_enabled=bool(
                    d.get("edge_ignore_enabled", cfg.postprocess.edge_ignore_enabled)
                ),
            )

        if "debug" in data:
            d = data["debug"]
            cfg.debug = DebugConfig(
                save_debug_image=bool(
                    d.get("save_debug_image", cfg.debug.save_debug_image)
                ),
                save_failed_image=bool(
                    d.get("save_failed_image", cfg.debug.save_failed_image)
                ),
                save_input_image=bool(
                    d.get("save_input_image", cfg.debug.save_input_image)
                ),
                debug_dir=str(d.get("debug_dir", cfg.debug.debug_dir)),
                failed_dir=str(d.get("failed_dir", cfg.debug.failed_dir)),
                max_keep_days=int(d.get("max_keep_days", cfg.debug.max_keep_days)),
            )

        if "logging" in data:
            d = data["logging"]
            cfg.logging = LoggingConfig(
                log_dir=str(d.get("log_dir", cfg.logging.log_dir)),
                level=str(d.get("level", cfg.logging.level)),
                rotation=str(d.get("rotation", cfg.logging.rotation)),
                retention=str(d.get("retention", cfg.logging.retention)),
            )

        logger.info("Config loaded from {}", path)
        return cfg

    def get_belt_polygon_points(self) -> list[float]:
        """Return belt polygon as a flat list of floats for OpenCV."""
        pts = []
        for p in self.belt_polygon:
            pts.extend([float(p[0]), float(p[1])])
        return pts

    def get_roi_rect(self) -> tuple[int, int, int, int]:
        """Return roi rect as (x1, y1, x2, y2)."""
        return (
            self.detect_roi_rect.x1,
            self.detect_roi_rect.y1,
            self.detect_roi_rect.x2,
            self.detect_roi_rect.y2,
        )

    def get_model_path(self) -> str:
        """Resolve model path. If starts with a relative dir, keep as-is
        (the caller resolves relative to working directory)."""
        return self.model.model_path


def get_root_dir() -> Path:
    """Return the project root directory (parent of app/).

    Tries: script directory -> cwd.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # When running as ``python -m app.main``, __file__ is app/main.py
    app_dir = Path(__file__).resolve().parent.parent
    return app_dir
