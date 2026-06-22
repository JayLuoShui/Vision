from __future__ import annotations

import time

from app.config import Config
from app.windows_app import ServiceController, run_diagnostics, window_title


class _FakeServer:
    def __init__(self, config, result_callback=None):
        self.config = config
        self.result_callback = result_callback
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True


def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached")


def test_service_controller_starts_and_stops_background_server():
    created = []

    def factory(config, result_callback=None):
        server = _FakeServer(config, result_callback)
        created.append(server)
        return server

    controller = ServiceController(Config(), server_factory=factory)
    controller.start()
    _wait_for(lambda: controller.snapshot().state == "running")

    assert created[0].started is True
    controller.stop()
    _wait_for(lambda: controller.snapshot().state == "stopped")
    assert created[0].stopped is True


def test_service_controller_restart_rebuilds_server_with_new_config():
    created = []

    def factory(config, result_callback=None):
        server = _FakeServer(config, result_callback)
        created.append(server)
        return server

    initial = Config()
    controller = ServiceController(initial, server_factory=factory)
    controller.start()
    _wait_for(lambda: controller.snapshot().state == "running")
    updated = Config()
    updated.service.tcp_port = 9200

    controller.restart(updated)
    _wait_for(
        lambda: controller.snapshot().state == "running" and len(created) == 2
    )

    assert created[0].stopped is True
    assert created[1].config.service.tcp_port == 9200
    controller.stop()


def test_service_controller_does_not_start_while_stopping():
    controller = ServiceController(Config(), server_factory=_FakeServer)
    controller._snapshot = controller._replace_snapshot(state="stopping")

    controller.start()

    assert controller.snapshot().state == "stopping"
    assert controller._thread is None


def test_service_controller_records_latest_result():
    controller = ServiceController(Config(), server_factory=_FakeServer)
    controller.record_result(
        {
            "task_id": "T100",
            "parcel_count": 2,
            "processing_time_ms": 78,
            "code": 0,
        }
    )

    snapshot = controller.snapshot()

    assert snapshot.request_count == 1
    assert snapshot.last_task_id == "T100"
    assert snapshot.last_parcel_count == 2
    assert snapshot.last_processing_time_ms == 78
    assert snapshot.error_count == 0


def test_run_diagnostics_succeeds_when_model_is_loaded(tmp_path):
    class _LoadedBackend:
        @staticmethod
        def is_loaded():
            return True

    class _Counter:
        def __init__(self, _config):
            self.backend = _LoadedBackend()

        def load(self):
            return None

    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")

    assert run_diagnostics(tmp_path, counter_factory=_Counter) == 0


def test_run_diagnostics_fails_when_model_is_not_loaded(tmp_path):
    class _MissingBackend:
        @staticmethod
        def is_loaded():
            return False

    class _Counter:
        def __init__(self, _config):
            self.backend = _MissingBackend()

        def load(self):
            return None

    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")

    assert run_diagnostics(tmp_path, counter_factory=_Counter) == 1


def test_window_title_contains_release_version():
    config = Config()
    config.service.version = "1.0.1"

    assert window_title(config) == "DWS 视觉计数服务 v1.0.1"
