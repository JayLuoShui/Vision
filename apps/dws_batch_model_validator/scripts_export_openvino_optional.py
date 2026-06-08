# -*- coding: utf-8 -*-
# Optional helper: export PT to OpenVINO for later CPU deployment comparison.
# Before INT8 export, replace data=... with your real dataset yaml for calibration.

from ultralytics import YOLO

model = YOLO("models/yolo26s-seg.pt")
model.export(
    format="openvino",
    imgsz=(736, 960),
    int8=True,
    data="configs/dataset.yaml",
    batch=1,
    dynamic=False,
)
