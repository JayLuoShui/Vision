from __future__ import annotations

from dws_validator.decision import decide
from dws_validator.predictor import Detection


def det(conf: float) -> Detection:
    return Detection(xyxy=(0, 0, 10, 10), conf=conf, cls=0)


def test_pred_count_at_least_two_is_multi():
    result = decide([det(0.8), det(0.7)], low_conf=0.25, high_conf=0.55)

    assert result.pred_count == 2
    assert result.status == "MULTI"
    assert result.signal == "INTERCEPT"


def test_one_high_and_one_suspect_is_suspect_multi():
    result = decide([det(0.8), det(0.35)], low_conf=0.25, high_conf=0.55)

    assert result.pred_count == 1
    assert result.suspect_count == 1
    assert result.status == "SUSPECT_MULTI"
    assert result.signal == "INTERCEPT_REVIEW"


def test_one_high_is_single():
    result = decide([det(0.8)], low_conf=0.25, high_conf=0.55)

    assert result.pred_count == 1
    assert result.status == "SINGLE"
    assert result.signal == "PASS"


def test_no_high_confidence_detection_is_unknown():
    result = decide([], low_conf=0.25, high_conf=0.55)

    assert result.pred_count == 0
    assert result.status == "UNKNOWN"
    assert result.signal == "REVIEW"
