from __future__ import annotations

from dws_validator.metrics import summarize


def test_summary_metrics_are_calculated():
    rows = [
        {"gt_count": 1, "is_correct": "1", "is_multi_gt": "0", "is_multi_pred": "0", "status": "SINGLE", "total_ms": 10},
        {"gt_count": 2, "is_correct": "1", "is_multi_gt": "1", "is_multi_pred": "1", "status": "MULTI", "total_ms": 20},
        {"gt_count": 2, "is_correct": "0", "is_multi_gt": "1", "is_multi_pred": "0", "status": "SINGLE", "total_ms": 30},
        {"gt_count": "", "is_correct": "", "is_multi_gt": "", "is_multi_pred": "", "status": "UNKNOWN", "total_ms": 40},
    ]

    summary = summarize(rows)

    assert summary["total_images"] == 4
    assert summary["labeled_images"] == 3
    assert summary["count_accuracy"] == 0.666667
    assert summary["multi_gt_images"] == 2
    assert summary["multi_recall"] == 0.5
    assert summary["status_counts"] == {"SINGLE": 2, "MULTI": 1, "UNKNOWN": 1}
    assert summary["p50_ms"] == 25.0
    assert summary["p95_ms"] == 38.5
