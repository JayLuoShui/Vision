from ultralytics import YOLO

model = YOLO("D:/Demo/Vision/weights/yolo26-s-seg-best_int8_openvino_model")
results = model.predict("datasets/test/Hikrobot MV-PD010003-12C-8C (DA8401808)_054455940_1418_4456290_Panorama.jpg", imgsz=(736, 960), device="cpu")

for r in results:
    print(r.boxes)
    print(r.masks)
