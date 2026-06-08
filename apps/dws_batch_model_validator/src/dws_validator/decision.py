# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import List
from .predictor import Detection


@dataclass
class Decision:
    pred_count: int
    suspect_count: int
    status: str
    signal: str
    confidence: float
    reasons: List[str]


def decide(detections: List[Detection], *, low_conf: float, high_conf: float) -> Decision:
    high = [d for d in detections if d.conf >= high_conf]
    suspect = [d for d in detections if low_conf <= d.conf < high_conf]

    pred_count = len(high)
    suspect_count = len(suspect)
    top_conf = max([d.conf for d in detections], default=0.0)

    reasons = []
    if pred_count >= 2:
        status = "MULTI"
        signal = "INTERCEPT"
        reasons.append(f"high_conf_instances={pred_count} >= 2")
    elif pred_count == 1 and suspect_count >= 1:
        status = "SUSPECT_MULTI"
        signal = "INTERCEPT_REVIEW"
        reasons.append("one high-confidence parcel plus low-confidence second candidate")
    elif pred_count == 1:
        status = "SINGLE"
        signal = "PASS"
        reasons.append("exactly one high-confidence parcel")
    else:
        status = "UNKNOWN"
        signal = "REVIEW"
        if suspect_count >= 1:
            reasons.append("only low-confidence candidates found")
        else:
            reasons.append("no valid parcel candidate found")

    return Decision(
        pred_count=pred_count,
        suspect_count=suspect_count,
        status=status,
        signal=signal,
        confidence=float(top_conf),
        reasons=reasons,
    )
