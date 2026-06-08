"""Tests for app.utils.geometry - Geometry helpers."""

from __future__ import annotations


from app.utils.geometry import box_area, center_of_box, iou, point_in_polygon


class TestIoU:
    """Tests for IoU (Intersection over Union) calculation."""

    def test_identical_boxes(self):
        """IoU should be 1.0 for identical boxes."""
        box1 = [0, 0, 100, 100]
        box2 = [0, 0, 100, 100]
        assert abs(iou(box1, box2) - 1.0) < 1e-6

    def test_completely_disjoint_boxes(self):
        """IoU should be 0.0 for non-overlapping boxes."""
        box1 = [0, 0, 50, 50]
        box2 = [100, 100, 150, 150]
        assert abs(iou(box1, box2) - 0.0) < 1e-6

    def test_partially_overlapping_boxes(self):
        """Test IoU for partially overlapping boxes."""
        box1 = [0, 0, 100, 100]
        box2 = [50, 50, 150, 150]
        expected = 2500.0 / 17500.0
        assert abs(iou(box1, box2) - expected) < 1e-6

    def test_one_inside_another(self):
        """Test box completely inside another."""
        box1 = [0, 0, 200, 200]
        box2 = [50, 50, 100, 100]
        expected = 2500.0 / 40000.0
        assert abs(iou(box1, box2) - expected) < 1e-6

    def test_empty_box(self):
        """Handle empty or invalid box."""
        box1 = [0, 0, 0, 0]
        box2 = [100, 100, 200, 200]
        assert iou(box1, box2) == 0.0

    def test_touching_edges(self):
        """Boxes that only share an edge should have IoU=0."""
        box1 = [0, 0, 100, 100]
        box2 = [100, 0, 200, 100]
        assert iou(box1, box2) == 0.0


class TestBoxArea:
    """Tests for box area calculation."""

    def test_normal_box(self):
        """Test normal box area."""
        assert box_area(10, 20, 110, 120) == 10000

    def test_square_box(self):
        """Test square box."""
        assert box_area(0, 0, 50, 50) == 2500

    def test_invalid_box(self):
        """Handle invalid box dimensions."""
        assert box_area(100, 200, 50, 100) == 0

    def test_negative_coordinates(self):
        """Invalid boxes with negative span return 0."""
        assert box_area(50, 50, 10, 10) == 0


class TestPointInPolygon:
    """Tests for point-in-polygon check."""

    def test_point_inside_square(self):
        """Point clearly inside a square polygon."""
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert point_in_polygon(50, 50, polygon) is True

    def test_point_outside_square(self):
        """Point clearly outside."""
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        assert point_in_polygon(200, 200, polygon) is False

    def test_point_on_boundary(self):
        """Point on boundary - implementation defined (may vary)."""
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        # ray casting may or may not include boundary; check non-boundary
        assert point_in_polygon(1, 1, polygon) is True

    def test_point_in_triangle(self):
        """Point inside a triangle."""
        polygon = [[0, 0], [100, 0], [50, 100]]
        assert point_in_polygon(50, 30, polygon) is True

    def test_point_in_triangle_outside(self):
        """Point outside triangle."""
        polygon = [[0, 0], [100, 0], [50, 100]]
        assert point_in_polygon(50, 150, polygon) is False

    def test_empty_polygon(self):
        """Empty polygon should return False."""
        assert point_in_polygon(0, 0, []) is False


class TestCenterOfBox:
    """Tests for box center calculation."""

    def test_normal_box(self):
        """Test center of a normal box."""
        cx, cy = center_of_box(10, 20, 110, 120)
        assert cx == 60.0
        assert cy == 70.0

    def test_zero_offset_box(self):
        """Box starting from origin."""
        cx, cy = center_of_box(0, 0, 100, 100)
        assert cx == 50.0
        assert cy == 50.0

    def test_float_coordinates(self):
        """Test with odd coordinates producing fractional centers."""
        cx, cy = center_of_box(1, 1, 4, 5)
        assert cx == 2.5
        assert cy == 3.0


class TestIntegration:
    """Integration-style tests combining geometry functions."""

    def test_center_in_polygon(self):
        """Use center_of_box + point_in_polygon together."""
        box = [100, 100, 200, 200]
        polygon = [[0, 0], [300, 0], [300, 300], [0, 300]]
        cx, cy = center_of_box(*box)
        assert point_in_polygon(cx, cy, polygon) is True

    def test_iou_with_identical_small_boxes(self):
        """Small identical boxes should have IoU=1."""
        box1 = [10, 10, 20, 20]
        box2 = [10, 10, 20, 20]
        assert iou(box1, box2) == 1.0
