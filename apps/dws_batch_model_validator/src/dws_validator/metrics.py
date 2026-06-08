# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np


def is_multi_count(count: Optional[int], multi_gt_min_count: int = 2) -> Optional[bool]:
    if count is None:
        return None
    return int(count) >= multi_gt_min_count


def pred_status_is_multi(status: str) -> bool:
    return status in {"MULTI", "SUSPECT_MULTI"}


def summarize(rows: List[Dict[str, Any]], multi_gt_min_count: int = 2) -> Dict[str, Any]:
    total_images = len(rows)
    labeled = [r for r in rows if r.get("gt_count") not in (None, "")]
    labeled_images = len(labeled)

    correct_rows = [r for r in labeled if r.get("is_correct") == "1"]
    count_accuracy = (len(correct_rows) / labeled_images) if labeled_images else None

    multi_gt_rows = [r for r in labeled if r.get("is_multi_gt") == "1"]
    multi_hit_rows = [r for r in multi_gt_rows if r.get("is_multi_pred") == "1"]
    multi_recall = (len(multi_hit_rows) / len(multi_gt_rows)) if multi_gt_rows else None

    ms = np.array([float(r["total_ms"]) for r in rows], dtype=np.float64) if rows else np.array([])

    status_counts: Dict[str, int] = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    return {
        "total_images": total_images,
        "labeled_images": labeled_images,
        "count_accuracy": None if count_accuracy is None else round(float(count_accuracy), 6),
        "multi_gt_images": len(multi_gt_rows),
        "multi_recall": None if multi_recall is None else round(float(multi_recall), 6),
        "mean_ms": None if ms.size == 0 else round(float(np.mean(ms)), 3),
        "p50_ms": None if ms.size == 0 else round(float(np.percentile(ms, 50)), 3),
        "p95_ms": None if ms.size == 0 else round(float(np.percentile(ms, 95)), 3),
        "max_ms": None if ms.size == 0 else round(float(np.max(ms)), 3),
        "status_counts": status_counts,
    }
