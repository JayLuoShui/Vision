from __future__ import annotations

from app.config import (
    CameraConfig,
    Config,
    DebugConfig,
    DetectROIRect,
    IgnoreRegion,
    LoggingConfig,
    ModelConfig,
    PostprocessConfig,
    PreprocessConfig,
    ServiceConfig,
)


def test_default_decode_reduce_factor_preserves_quality_baseline():
    assert Config().service.decode_reduce_factor == 1


def test_to_yaml_round_trips_all_config_fields(tmp_path):
    expected = Config(
        camera=CameraConfig(raw_width=1920, raw_height=1080),
        service=ServiceConfig(
            name="视觉计数服务",
            version="2.3.4",
            host="127.0.0.1",
            http_port=18080,
            tcp_port=19100,
            request_timeout_ms=4500,
            max_image_bytes=12_345_678,
            default_image_encoding="raw",
            decode_reduce_factor=4,
        ),
        model=ModelConfig(
            backend="native_openvino",
            model_path="模型/包裹检测",
            device="AUTO",
            imgsz=1280,
            batch=2,
            performance_hint="THROUGHPUT",
            inference_num_threads=8,
            confidence_threshold=0.35,
            iou_threshold=0.60,
            class_names={"0": "包裹", "1": "托盘"},
            target_class_name="包裹",
        ),
        preprocess=PreprocessConfig(
            mode="tile_2x2",
            infer_imgsz=1280,
            keep_ratio=False,
            normalize=False,
            mask_outside_polygon=False,
            mask_ignore_regions=False,
            tile_overlap_ratio=0.25,
        ),
        detect_roi_rect=DetectROIRect(x1=10, y1=20, x2=1800, y2=900),
        belt_polygon=[[10, 20], [1800, 20], [1700, 900], [100, 900]],
        ignore_regions=[
            IgnoreRegion(name="顶部文字", x1=0, y1=0, x2=300, y2=100),
            IgnoreRegion(name="右侧设备", x1=1600, y1=100, x2=1920, y2=800),
        ],
        postprocess=PostprocessConfig(
            count_by="box",
            min_box_area_raw=4000,
            min_mask_area_raw=3500,
            duplicate_iou_threshold=0.65,
            duplicate_mask_iou_threshold=0.66,
            duplicate_mask_overlap_threshold=0.20,
            require_center_in_belt_polygon=False,
            edge_ignore_enabled=True,
        ),
        debug=DebugConfig(
            save_debug_image=False,
            save_failed_image=False,
            save_input_image=True,
            debug_dir="调试/图片",
            failed_dir="缓存/失败",
            max_keep_days=30,
        ),
        logging=LoggingConfig(
            log_dir="日志",
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
        ),
    )
    path = tmp_path / "config.yaml"

    expected.to_yaml(path)

    assert Config.from_yaml(path) == expected


def test_to_yaml_writes_unicode_as_utf8_text(tmp_path):
    path = tmp_path / "config.yaml"
    config = Config(service=ServiceConfig(name="视觉计数服务"))

    config.to_yaml(path)

    raw = path.read_bytes()
    assert "视觉计数服务".encode("utf-8") in raw
    assert raw.decode("utf-8")
