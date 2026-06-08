"""Pytest fixtures and configuration for the test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import cv2

from app.config import Config
from app.vision.runner import VisionRunner
from app.vision.backends.base import BaseVisionBackend


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def test_image_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return path to a test image for tests.

    Creates a synthetic BGR image (3036x4024, matching real camera) 
    as a temporary JPEG file. File-scoped so it persists across tests.
    """
    img = np.random.randint(0, 255, (3036, 4024, 3), dtype=np.uint8)
    path = tmp_path_factory.getbasetemp() / "test_image.jpeg"
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture(scope="session")
def config() -> Config:
    """Return a default Config instance (uses dataclass defaults)."""
    return Config()


@pytest.fixture
def mock_backend() -> MagicMock:
    """Return a MagicMock for the current vision backend contract.

    Configured with ``is_loaded() -> True`` so the runner pipeline doesn't
    crash on a missing model.  All methods return harmless defaults.
    """
    backend = MagicMock(spec=BaseVisionBackend)
    backend.is_loaded.return_value = True
    backend.predict.return_value = []
    return backend


@pytest.fixture
def runner(config: Config, mock_backend: MagicMock) -> Generator[VisionRunner, None, None]:
    """Yield a VisionRunner with a mocked backend (no real model loaded).

    Patches ``ParcelCounter._create_backend`` so the expensive
    OpenVINO / Ultralytics model never loads during tests.
    """
    with patch(
        "app.vision.counter.ParcelCounter._create_backend",
        return_value=mock_backend,
    ):
        r = VisionRunner(config)
        yield r


@pytest.fixture
def sample_image_bytes(test_image_path: Path) -> bytes:
    """Read the test image as bytes."""
    return test_image_path.read_bytes()


@pytest.fixture
def sample_metadata() -> dict:
    """Sample metadata dict for tests."""
    return {
        "task_id": "test-task-001",
        "barcode": "PARCEL-123456",
        "timestamp": "2025-01-01T00:00:00Z",
        "image_encoding": "encoded",
        "image_len": 1024,
        "image_type": "bgr",
    }
