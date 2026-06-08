# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Dict, List, Optional
import csv
import json
import shutil
import traceback

from tqdm import tqdm

from .config import RuntimeConfig
from .decision import decide
from .labels import count_yolo_instances, label_path_for_image
from .metrics import is_multi_count, pred_status_is_multi, summarize
from .predictor import YoloSegPredictor, resolve_model_path_for_ultralytics
from .signal_mock import send_signal_mock
from .visualize import draw_result, read_image_bgr


CSV_FIELDS = [
    "image",
    "pred_count",
    "suspect_count",
    "status",
    "signal",
    "confidence",
    "gt_count",
    "is_correct",
    "is_multi_gt",
    "is_multi_pred",
    "read_ms",
    "preprocess_ms",
    "infer_ms",
    "post_ms",
    "signal_ms",
    "total_ms",
    "vis_path",
    "error_type",
    "reasons",
]


ProgressCallback = Callable[[int, int, str, dict[str, Any]], None]
LogCallback = Callable[[str], None]
CancelCallback = Callable[[], bool]


def make_run_dir(base_dir: str | Path) -> Path:
    base = Path(base_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / stamp
    idx = 1
    while run_dir.exists():
        run_dir = base / f"{stamp}_{idx:02d}"
        idx += 1
    (run_dir / "vis").mkdir(parents=True, exist_ok=True)
    (run_dir / "errors" / "false_single").mkdir(parents=True, exist_ok=True)
    (run_dir / "errors" / "false_multi").mkdir(parents=True, exist_ok=True)
    (run_dir / "errors" / "unknown").mkdir(parents=True, exist_ok=True)
    return run_dir


def list_images(images_dir: Path, exts: List[str]) -> List[Path]:
    exts = [e.lower() for e in exts]
    images = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
    return sorted(images)


def _bool_or_empty(x: Optional[bool]) -> str:
    if x is None:
        return ""
    return "1" if bool(x) else "0"


def _error_type(gt_count: Optional[int], status: str) -> str:
    if status == "UNKNOWN":
        return "unknown"
    if gt_count is None:
        return ""
    gt_multi = gt_count >= 2
    pred_multi = pred_status_is_multi(status)
    if gt_multi and not pred_multi:
        return "false_single"
    if (not gt_multi) and pred_multi:
        return "false_multi"
    return ""


def _copy_error_image(src_vis_path: Path, image_path: Path, run_dir: Path, error_type: str) -> None:
    if not error_type:
        return
    target = run_dir / "errors" / error_type / image_path.name
    if src_vis_path.exists():
        shutil.copy2(src_vis_path, target)


def _log(log_cb: LogCallback | None, message: str) -> None:
    if log_cb:
        log_cb(message)
    else:
        print(message)


def _validate_inputs(cfg: RuntimeConfig) -> None:
    images_dir = Path(cfg.images_dir)
    labels_dir = Path(cfg.labels_dir)
    output_dir = Path(cfg.output_base_dir)
    resolve_model_path_for_ultralytics(cfg.model_path)
    if not images_dir.exists():
        raise FileNotFoundError(f"图片目录不存在：{images_dir}")
    if not labels_dir.exists():
        raise FileNotFoundError(f"标签目录不存在：{labels_dir}")
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".write_probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise OSError(f"输出目录不可写，请选择用户目录下的其他位置：{output_dir}") from exc


def _unknown_row(image_name: str, reason: str, total_ms: float, read_ms: float = 0.0) -> dict[str, Any]:
    return {
        "image": image_name,
        "pred_count": 0,
        "suspect_count": 0,
        "status": "UNKNOWN",
        "signal": "REVIEW",
        "confidence": 0.0,
        "gt_count": "",
        "is_correct": "",
        "is_multi_gt": "",
        "is_multi_pred": "",
        "read_ms": round(read_ms, 3),
        "preprocess_ms": 0.0,
        "infer_ms": 0.0,
        "post_ms": 0.0,
        "signal_ms": 0.0,
        "total_ms": round(total_ms, 3),
        "vis_path": "",
        "error_type": "unknown",
        "reasons": reason,
    }


def run_batch(
    cfg: RuntimeConfig,
    progress_cb: ProgressCallback | None = None,
    log_cb: LogCallback | None = None,
    cancel_cb: CancelCallback | None = None,
) -> Dict[str, Any]:
    _validate_inputs(cfg)
    images_dir = Path(cfg.images_dir)
    labels_dir = Path(cfg.labels_dir)

    run_dir = make_run_dir(cfg.output_base_dir)
    vis_dir = run_dir / "vis"
    results_csv = run_dir / "results.csv"
    summary_json = run_dir / "summary.json"
    config_json = run_dir / "resolved_config.json"
    failed_csv = run_dir / "failed_items.csv"

    config_json.write_text(json.dumps(cfg.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")

    images = list_images(images_dir, cfg.image_exts or [])
    if not images:
        raise RuntimeError(f"图片目录为空或没有支持的图片文件：{images_dir}")

    _log(log_cb, f"图片数量：{len(images)}")
    _log(log_cb, f"模型：{cfg.model_path}")
    _log(log_cb, f"输入尺寸：({cfg.imgsz_h}, {cfg.imgsz_w})")
    _log(log_cb, f"设备策略：{cfg.device}")
    _log(log_cb, f"阈值：low={cfg.low_conf}, high={cfg.high_conf}, iou={cfg.iou}")
    _log(log_cb, f"输出目录：{run_dir}")
    _log(log_cb, "正在加载模型...")

    predictor = YoloSegPredictor(
        model_path=cfg.model_path,
        imgsz_h=cfg.imgsz_h,
        imgsz_w=cfg.imgsz_w,
        device=cfg.device,
        half=cfg.half,
        retina_masks=cfg.retina_masks,
    )
    _log(log_cb, f"实际推理设备：{predictor.actual_device_label}")

    rows: List[Dict[str, Any]] = []
    cancelled = False

    with results_csv.open("w", newline="", encoding="utf-8-sig") as result_file, failed_csv.open("w", newline="", encoding="utf-8-sig") as failed_file:
        writer = csv.DictWriter(result_file, fieldnames=CSV_FIELDS)
        failed_writer = csv.DictWriter(failed_file, fieldnames=["image", "error", "traceback"])
        writer.writeheader()
        failed_writer.writeheader()
        iterator = enumerate(images, start=1)
        if progress_cb is None:
            iterator = enumerate(tqdm(images, desc="DWS batch validating"), start=1)

        for index, img_path in iterator:
            if cancel_cb and cancel_cb():
                cancelled = True
                _log(log_cb, f"任务已取消，已完成 {len(rows)}/{len(images)}。")
                break

            t_start = perf_counter()
            try:
                t0 = perf_counter()
                image = read_image_bgr(img_path)
                read_ms = (perf_counter() - t0) * 1000.0
                if image is None:
                    row = _unknown_row(img_path.name, "图片读取失败", (perf_counter() - t_start) * 1000.0, read_ms)
                    failed_writer.writerow({"image": img_path.name, "error": "图片读取失败", "traceback": ""})
                else:
                    t0 = perf_counter()
                    preprocess_ms = (perf_counter() - t0) * 1000.0

                    t0 = perf_counter()
                    detections, _raw_result = predictor.predict(image, low_conf=cfg.low_conf, iou=cfg.iou)
                    infer_ms = (perf_counter() - t0) * 1000.0

                    t0 = perf_counter()
                    decision = decide(detections, low_conf=cfg.low_conf, high_conf=cfg.high_conf)
                    gt_count = count_yolo_instances(label_path_for_image(img_path, labels_dir))
                    is_correct: Optional[bool] = None
                    if gt_count is not None:
                        is_correct = int(decision.pred_count) == int(gt_count)
                    is_multi_gt = is_multi_count(gt_count, cfg.multi_gt_min_count)
                    is_multi_pred = pred_status_is_multi(decision.status)
                    error_type = _error_type(gt_count, decision.status)
                    post_ms = (perf_counter() - t0) * 1000.0

                    signal_payload = {
                        "image": img_path.name,
                        "package_count": decision.pred_count,
                        "status": decision.status,
                        "signal": decision.signal,
                        "confidence": decision.confidence,
                    }
                    signal_ms = send_signal_mock(signal_payload, cfg.mock_delay_ms)
                    total_ms = (perf_counter() - t_start) * 1000.0

                    vis_path = ""
                    preview_path = ""
                    should_save_vis = cfg.save_vis and (cfg.vis_all or decision.status != "SINGLE" or bool(error_type))
                    if should_save_vis:
                        out_vis = vis_dir / img_path.name
                        try:
                            draw_result(
                                image,
                                detections,
                                decision,
                                total_ms,
                                out_vis,
                                high_conf=cfg.high_conf,
                                low_conf=cfg.low_conf,
                                gt_count=gt_count,
                            )
                            vis_path = str(out_vis.relative_to(run_dir))
                            preview_path = str(out_vis)
                            if cfg.save_error_images:
                                _copy_error_image(out_vis, img_path, run_dir, error_type)
                        except Exception as exc:  # noqa: BLE001
                            failed_writer.writerow({"image": img_path.name, "error": f"可视化图片写入失败：{exc}", "traceback": traceback.format_exc()})
                            _log(log_cb, f"{img_path.name} 可视化写入失败：{exc}")

                    row = {
                        "image": img_path.name,
                        "pred_count": decision.pred_count,
                        "suspect_count": decision.suspect_count,
                        "status": decision.status,
                        "signal": decision.signal,
                        "confidence": round(decision.confidence, 6),
                        "gt_count": "" if gt_count is None else int(gt_count),
                        "is_correct": _bool_or_empty(is_correct),
                        "is_multi_gt": _bool_or_empty(is_multi_gt),
                        "is_multi_pred": _bool_or_empty(is_multi_pred),
                        "read_ms": round(read_ms, 3),
                        "preprocess_ms": round(preprocess_ms, 3),
                        "infer_ms": round(infer_ms, 3),
                        "post_ms": round(post_ms, 3),
                        "signal_ms": round(signal_ms, 3),
                        "total_ms": round(total_ms, 3),
                        "vis_path": vis_path,
                        "error_type": error_type,
                        "reasons": "; ".join(decision.reasons),
                    }
                    row["_preview_path"] = preview_path
            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc()
                total_ms = (perf_counter() - t_start) * 1000.0
                row = _unknown_row(img_path.name, f"推理过程异常：{exc}", total_ms)
                failed_writer.writerow({"image": img_path.name, "error": str(exc), "traceback": tb})
                _log(log_cb, f"{img_path.name} 处理失败：{exc}")

            rows.append(row)
            writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})
            result_file.flush()
            failed_file.flush()

            callback_row = dict(row)
            if progress_cb:
                progress_cb(index, len(images), img_path.name, callback_row)
            _log(log_cb, f"{img_path.name} | {row['status']} | signal={row['signal']} | total={row['total_ms']} ms")

    summary = summarize(rows, multi_gt_min_count=cfg.multi_gt_min_count)
    summary["run_dir"] = str(run_dir)
    summary["results_csv"] = str(results_csv)
    summary["config"] = cfg.__dict__
    summary["cancelled"] = cancelled

    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(log_cb, "========== SUMMARY ==========")
    _log(log_cb, json.dumps(summary, ensure_ascii=False, indent=2))
    _log(log_cb, f"results.csv：{results_csv}")
    _log(log_cb, f"summary.json：{summary_json}")
    return summary
