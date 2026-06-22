from __future__ import annotations

import numpy as np

from app.schemas import CountObject
from app.utils.debug_draw import draw_debug_image


def test_debug_draw_scales_original_coordinates_to_reduced_image():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    obj = CountObject(
        class_id=0,
        class_name="parcel",
        score=0.9,
        box=[40, 40, 160, 160],
        center=[100, 100],
        box_area=14400,
    )
    output = draw_debug_image(
        image,
        [obj],
        [[0, 0], [200, 0], [200, 200], [0, 200]],
        parcel_count=1,
        processing_time_ms=10,
        original_width=200,
        original_height=200,
    )
    assert output[20, 20, 1] > 0
