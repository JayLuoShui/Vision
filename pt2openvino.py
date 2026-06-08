from ultralytics import YOLO

model = YOLO("D:\\Demo\\Vision\\weights\\yolo26s-seg-wds-1024-best.pt")

model.export(
    format="openvino",
    imgsz=(1024, 1024),
    int8=True,
    data="datasets/cvds_20260512_yolomask/data.yaml",
    batch=1,
    dynamic=False,
)
