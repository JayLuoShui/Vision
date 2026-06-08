"""Metrics tracker for service statistics."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricsTracker:
    """Thread-safe metrics for processing times and counts."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _processing_times: deque[int] = field(default_factory=lambda: deque(maxlen=1000))
    _last_task_time: Optional[str] = None
    _total_tasks: int = 0
    _total_errors: int = 0

    @property
    def avg_processing_time_ms(self) -> float:
        """Average processing time in ms over recent requests."""
        with self._lock:
            if not self._processing_times:
                return 0.0
            return sum(self._processing_times) / len(self._processing_times)

    @property
    def last_task_time(self) -> Optional[str]:
        return self._last_task_time

    @last_task_time.setter
    def last_task_time(self, value: str) -> None:
        with self._lock:
            self._last_task_time = value

    def record_processing_time(self, ms: int) -> None:
        """Record a single processing time measurement."""
        with self._lock:
            self._processing_times.append(ms)
            self._total_tasks += 1

    def record_error(self) -> None:
        with self._lock:
            self._total_errors += 1

    def get_stats(self) -> dict:
        """Return a summary dict of current metrics."""
        with self._lock:
            times = list(self._processing_times)
            return {
                "total_tasks": self._total_tasks,
                "total_errors": self._total_errors,
                "avg_processing_time_ms": (
                    sum(times) / len(times) if times else 0.0
                ),
                "last_task_time": self._last_task_time,
            }
