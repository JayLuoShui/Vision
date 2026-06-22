"""Time utility functions.

Provides millisecond timestamps, elapsed-time helpers, a context-manager
Timer, and a simple benchmark decorator for performance measurement.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from typing import Any


# ── basic timestamp helpers ────────────────────────────────────────

def now_ms() -> int:
    """Return current time in milliseconds (integer)."""
    return int(time.time() * 1000)


def elapsed_ms(start_ms: int) -> int:
    """Return elapsed milliseconds since start_ms.

    Args:
        start_ms: Start time from now_ms().

    Returns:
        Elapsed milliseconds since start_ms.
    """
    return now_ms() - start_ms


# ── Timer context manager ─────────────────────────────────────────

class Timer:
    """Context manager that measures and stores elapsed ms.

    Usage ::

        with Timer() as t:
            sleep(0.12)
        assert t.elapsed_ms() >= 100
    """

    def __enter__(self) -> "Timer":
        self._start_ms: int = now_ms()
        return self

    def __exit__(self, *args: Any) -> None:
        self._elapsed_ms: int = elapsed_ms(self._start_ms)

    def elapsed_ms(self) -> int:
        """Return the elapsed time in milliseconds (0 if context not exited yet)."""
        return getattr(self, "_elapsed_ms", 0)


# ── benchmark decorator ───────────────────────────────────────────

def benchmark(func: Callable) -> Callable:
    """Decorator that records the execution time (ms) as ``func._benchmark_ms``.

    The measured time is updated on every call.  If the decorated
    function is called multiple times, the *last* invocation time is
    stored (use ``Timer`` instead for aggregate stats).
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = now_ms()
        result = func(*args, **kwargs)
        wrapper._benchmark_ms = elapsed_ms(start)
        return result

    wrapper._benchmark_ms = 0  # type: ignore[attr-defined]
    return wrapper


# ── timing decorator (alias + log) ────────────────────────────────

def timing(name: str = "") -> Callable:
    """Decorator that calls ``func`` and prints (log) elapsed ms.

    Intended for quick debugging; returns the *original* result.

    Usage ::

        @timing("slow_op")
        def slow_op(): ...

    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = now_ms()
            result = func(*args, **kwargs)
            elapsed = elapsed_ms(start)
            label = name or func.__qualname__
            print(f"[timing] {label}: {elapsed} ms")  # noqa: T201
            return result

        return wrapper

    return decorator
