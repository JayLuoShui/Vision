from __future__ import annotations

from app.config import Config
from app.logger import setup_logging


def test_setup_logging_supports_windowed_application_without_stderr(
    monkeypatch,
    tmp_path,
):
    config = Config()
    config.logging.log_dir = str(tmp_path)
    monkeypatch.setattr("app.logger.sys.stderr", None)
    monkeypatch.setattr("app.logger.get_root_dir", lambda: tmp_path)

    setup_logging(config)

    assert (tmp_path / "service.log").exists()
    assert (tmp_path / "error.log").exists()


def test_setup_logging_ignores_non_writable_stderr(monkeypatch, tmp_path):
    config = Config()
    config.logging.log_dir = str(tmp_path)
    monkeypatch.setattr("app.logger.sys.stderr", object())
    monkeypatch.setattr("app.logger.get_root_dir", lambda: tmp_path)

    setup_logging(config)

    assert (tmp_path / "service.log").exists()
