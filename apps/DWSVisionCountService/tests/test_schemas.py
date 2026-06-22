"""Tests for app.schemas - Pydantic models for requests/responses."""

from __future__ import annotations


import numpy as np

from app.schemas import (
    CountObject,
    CountResult,
    DecodedImage,
    Detection,
    ImageMeta,
)


class TestImageMeta:
    """Tests for ImageMeta model."""

    def test_required_only(self):
        """Test creating ImageMeta with only required field."""
        meta = ImageMeta(task_id="test-123")
        assert meta.task_id == "test-123"
        assert meta.timestamp is None
        assert meta.barcode is None
        assert meta.image_encoding == "encoded"

    def test_all_fields(self):
        """Test creating ImageMeta with all fields."""
        meta = ImageMeta(
            task_id="full-test",
            timestamp="2025-01-01",
            barcode="PARCEL-ABC",
            image_encoding="raw",
            image_len=1024,
            width=1920,
            height=1080,
            channels=3,
            pixel_format="bgr",
            dws_meta={"extra": "data"},
        )
        assert meta.task_id == "full-test"
        assert meta.barcode == "PARCEL-ABC"
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.channels == 3

    def test_validate_image_encoding(self):
        """Test image_encoding validation."""
        meta = ImageMeta(task_id="enc-123", image_encoding="b64")
        assert meta.image_encoding == "b64"

        meta2 = ImageMeta(task_id="enc-456", image_encoding="raw")
        assert meta2.image_encoding == "raw"


class TestDecodedImage:
    """Tests for DecodedImage model."""

    def test_create(self):
        """Test creating DecodedImage."""
        img = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
        decoded = DecodedImage(
            task_id="task-123",
            image_bgr=img,
            width=128,
            height=128,
            source_encoding="bgr",
        )
        assert decoded.width == 128
        assert decoded.height == 128
        assert decoded.source_encoding == "bgr"
        assert decoded.image_bgr.shape == (128, 128, 3)


class TestDetection:
    """Tests for Detection model."""

    def test_minimal_detection(self):
        """Test minimal Detection object."""
        det = Detection(
            class_id=0,
            class_name="parcel",
            score=0.85,
        )
        assert det.class_id == 0
        assert det.class_name == "parcel"
        assert det.score == 0.85
        assert det.box_model == []
        assert det.mask_model is None

    def test_full_detection(self):
        """Test Detection with mask."""
        mask = np.random.randint(0, 2, (64, 64), dtype=np.uint8)
        det = Detection(
            class_id=0,
            class_name="parcel",
            score=0.92,
            box_model=[100.0, 200.0, 300.0, 400.0],
            mask_model=mask,
            mask_area_model=500.0,
        )
        assert det.score == 0.92
        assert det.box_model == [100.0, 200.0, 300.0, 400.0]
        assert len(det.mask_model) > 0


class TestCountObject:
    """Tests for CountObject model."""

    def test_minimal(self):
        """Test minimal CountObject."""
        obj = CountObject(
            class_id=0,
            class_name="parcel",
            score=0.95,
        )
        assert obj.class_id == 0
        assert obj.box == []
        assert obj.center == []
        assert obj.box_area == 0.0

    def test_full(self):
        """Test CountObject with all fields."""
        obj = CountObject(
            class_id=0,
            class_name="parcel",
            score=0.95,
            box=[100.0, 200.0, 300.0, 400.0],
            center=[200.0, 300.0],
            box_area=40000.0,
            mask_area=35000.0,
        )
        assert obj.box == [100.0, 200.0, 300.0, 400.0]
        assert obj.center == [200.0, 300.0]
        assert obj.box_area == 40000.0


class TestCountResult:
    """Tests for CountResult model."""

    def test_empty_result(self):
        """Test successful empty result."""
        result = CountResult(
            task_id="test-empty",
            code=0,
            message="success",
        )
        assert result.task_id == "test-empty"
        assert result.code == 0
        assert result.parcel_count == 0
        assert len(result.objects) == 0

    def test_result_with_objects(self):
        """Test result with detection objects."""
        objects = [
            CountObject(class_id=0, class_name="parcel", score=0.95,
                       box=[100, 200, 300, 400], center=[200, 300]),
            CountObject(class_id=0, class_name="parcel", score=0.88,
                       box=[500, 600, 700, 800], center=[600, 700]),
        ]
        result = CountResult(
            task_id="test-two",
            code=0,
            message="success",
            parcel_count=2,
            confidence=0.915,
            processing_time_ms=45,
            objects=objects,
        )
        assert result.parcel_count == 2
        assert len(result.objects) == 2
        assert result.confidence == 0.915

    def test_error_result(self):
        """Test error result."""
        result = CountResult(
            task_id="test-error",
            code=1,
            message="decoding failed",
        )
        assert result.code == 1
        assert result.parcel_count == 0

    def test_to_dict(self):
        """Test serialization to dict."""
        objects = [
            CountObject(
                class_id=0,
                class_name="parcel",
                score=0.95,
                box=[100.0, 200.0, 300.0, 400.0],
                center=[200.0, 300.0],
                box_area=40000.0,
                mask_area=35000.0,
            ),
        ]
        result = CountResult(
            task_id="test-dict",
            code=0,
            message="ok",
            parcel_count=1,
            confidence=0.95,
            objects=objects,
        )
        
        d = result.to_dict()
        
        # Verify serialization
        assert "task_id" in d
        assert "parcel_count" in d
        assert "objects" in d
        assert len(d["objects"]) == 1
        assert d["objects"][0]["score"] == 0.95
        assert d["objects"][0]["box"] == [100.0, 200.0, 300.0, 400.0]
