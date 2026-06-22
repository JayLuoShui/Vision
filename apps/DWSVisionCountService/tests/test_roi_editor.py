from __future__ import annotations

import pytest

from app.roi_editor import CanvasTransform, ROIEditorState


def test_canvas_transform_fits_image_and_centers_letterbox():
    transform = CanvasTransform(image_size=(400, 200), canvas_size=(300, 300))

    assert transform.scale == pytest.approx(0.75)
    assert transform.rendered_size == pytest.approx((300.0, 150.0))
    assert transform.offset == pytest.approx((0.0, 75.0))
    assert transform.image_to_canvas((200, 100)) == pytest.approx((150.0, 150.0))
    assert transform.canvas_to_image((150, 150)) == pytest.approx((200.0, 100.0))


def test_canvas_transform_rejects_points_in_letterbox_margin():
    transform = CanvasTransform(image_size=(400, 200), canvas_size=(300, 300))

    with pytest.raises(ValueError, match="outside"):
        transform.canvas_to_image((150, 50))


def test_detect_rectangle_is_normalized_and_exported_as_image_integers():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
        mode="detect_rect",
    )

    state.add_rectangle((225, 187.5), (75, 112.5))

    assert state.export() == [100, 50, 300, 150]
    assert all(isinstance(value, int) for value in state.export())


def test_belt_polygon_requires_three_points_before_export():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
        mode="belt_polygon",
    )
    state.add_point((0, 75))
    state.add_point((300, 75))

    with pytest.raises(ValueError, match="at least 3"):
        state.export()

    state.add_point((150, 225))

    assert state.export() == [[0, 0], [400, 0], [200, 200]]


def test_ignore_rect_supports_multiple_rectangles_and_undo():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
        mode="ignore_rect",
    )
    state.add_rectangle((0, 75), (75, 112.5))
    state.add_rectangle((225, 187.5), (300, 225))

    assert state.export() == [[0, 0, 100, 50], [300, 150, 400, 200]]
    assert state.undo() is True
    assert state.export() == [[0, 0, 100, 50]]
    assert state.undo() is True
    assert state.export() == []
    assert state.undo() is False


def test_clear_only_affects_selected_mode_and_can_be_undone():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
        mode="detect_rect",
    )
    state.add_rectangle((0, 75), (300, 225))
    state.set_mode("ignore_rect")
    state.add_rectangle((0, 75), (75, 112.5))

    state.clear()

    assert state.export() == []
    assert state.export("detect_rect") == [0, 0, 400, 200]
    assert state.undo() is True
    assert state.export() == [[0, 0, 100, 50]]


def test_resizing_canvas_does_not_change_saved_image_coordinates():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
        mode="detect_rect",
    )
    state.add_rectangle((75, 112.5), (225, 187.5))

    state.set_canvas_size((800, 200))

    assert state.export() == [100, 50, 300, 150]
    assert state.transform.image_to_canvas((100, 50)) == pytest.approx((300, 50))


def test_load_existing_regions_keeps_original_image_coordinates():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
    )

    state.load_existing(
        detect_rect=(10, 20, 390, 180),
        belt_polygon=[(20, 30), (380, 30), (200, 170)],
        ignore_rects=[(0, 0, 100, 50)],
    )

    assert state.export("detect_rect") == [10, 20, 390, 180]
    assert state.export("belt_polygon") == [[20, 30], [380, 30], [200, 170]]
    assert state.export("ignore_rect") == [[0, 0, 100, 50]]
    assert state.undo() is False


def test_load_existing_rejects_regions_outside_image():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
    )

    with pytest.raises(ValueError, match="bounds"):
        state.load_existing(
            detect_rect=(0, 0, 401, 200),
            belt_polygon=[],
            ignore_rects=[],
        )


def test_mode_rejects_wrong_edit_operation_and_degenerate_rectangle():
    state = ROIEditorState(
        image_size=(400, 200),
        canvas_size=(300, 300),
        mode="detect_rect",
    )

    with pytest.raises(ValueError, match="belt_polygon"):
        state.add_point((150, 150))
    with pytest.raises(ValueError, match="non-zero"):
        state.add_rectangle((150, 150), (150, 150))
    with pytest.raises(ValueError, match="Unsupported"):
        state.set_mode("unknown")
