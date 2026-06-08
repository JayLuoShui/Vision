"""Tests for app.utils.time_utils - Timing helpers.

Covers now_ms, elapsed_ms, Timer context manager, benchmark decorator,
and timing decorator.
"""

from __future__ import annotations

import time


from app.utils.time_utils import Timer, benchmark, elapsed_ms, now_ms, timing


class TestNowMs:
    """Tests for now_ms()."""

    def test_returns_int(self):
        result = now_ms()
        assert isinstance(result, int)

    def test_returns_positive(self):
        result = now_ms()
        assert result > 0


class TestElapsedMs:
    """Tests for elapsed_ms()."""

    def test_immediate_elapsed(self):
        start = now_ms()
        elapsed = elapsed_ms(start)
        assert 0 <= elapsed < 100  # near-zero

    def test_after_sleep(self):
        start = now_ms()
        time.sleep(0.1)
        elapsed = elapsed_ms(start)
        assert elapsed >= 90  # allow small timing error


class TestTimer:
    """Tests for Timer context manager."""

    def test_timer_no_context_error(self):
        """Calling elapsed_ms() before exiting should return 0."""
        t = Timer()
        # __exit__ hasn't been called yet
        assert t.elapsed_ms() == 0

    def test_timer_basic(self):
        """Timer should measure >= 100ms after sleep(0.1)."""
        with Timer() as t:
            time.sleep(0.1)
        assert t.elapsed_ms() >= 80

    def test_timer_returns_self(self):
        """__enter__ should return self."""
        with Timer() as t:
            assert isinstance(t, Timer)

    def test_nested_timers(self):
        """Nested timers should measure independently."""
        with Timer() as outer:
            time.sleep(0.05)
            with Timer() as inner:
                time.sleep(0.05)
            assert inner.elapsed_ms() >= 40
        # outer timer exits here; now we can check elapsed_ms
        assert outer.elapsed_ms() >= 90


class TestBenchmark:
    """Tests for @benchmark decorator."""

    def test_benchmark_records_time(self):
        @benchmark
        def quick():
            time.sleep(0.05)
        quick()
        assert quick._benchmark_ms >= 40  # allow small error

    def test_benchmark_returns_original_result(self):
        @benchmark
        def add(a, b):
            return a + b
        assert add(3, 4) == 7

    def test_benchmark_no_args_func(self):
        @benchmark
        def zero_args():
            return "ok"
        assert zero_args() == "ok"


class TestTiming:
    """Tests for @timing decorator."""

    def test_timing_returns_original_result(self):
        @timing("test_fn")
        def add(a, b):
            return a + b
        assert add(1, 2) == 3

    def test_timing_prints_elapsed(self, capsys):  # noqa: PT019
        """timing decorator should print [timing] ... to stdout."""
        @timing("fast_op")
        def fast():
            return 1
        fast()
        captured = capsys.readouterr()
        assert "[timing]" in captured.out
        assert "fast_op" in captured.out

    def test_timing_uses_qualname_when_no_name(self, capsys):  # noqa: PT019
        """When no name provided, use function qualified name."""
        @timing()
        def my_custom_op():
            return 42
        my_custom_op()
        captured = capsys.readouterr()
        assert "my_custom_op" in captured.out
