from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_window_left_panel_is_scrollable_and_responsive():
    source = (ROOT / "src" / "dws_validator_gui" / "main_window.py").read_text(encoding="utf-8")

    assert "QScrollArea" in source
    assert "setWidgetResizable(True)" in source
    assert "setStretchFactor(0, 1)" in source
    assert "setCollapsible(0, False)" in source


def test_elapsed_display_uses_milliseconds():
    source = (ROOT / "src" / "dws_validator_gui" / "main_window.py").read_text(encoding="utf-8")

    assert '"0 ms"' in source
    assert "elapsed_ms" in source
    assert ".0f} ms" in source
    assert "0.0 s" not in source
