# -*- coding: utf-8 -*-
from __future__ import annotations

from time import perf_counter, sleep
from typing import Dict, Any


def send_signal_mock(payload: Dict[str, Any], mock_delay_ms: float = 0.0) -> float:
    """Mock DWS signal sender. Returns elapsed milliseconds."""
    t0 = perf_counter()
    if mock_delay_ms > 0:
        sleep(mock_delay_ms / 1000.0)
    _ = payload
    return (perf_counter() - t0) * 1000.0
