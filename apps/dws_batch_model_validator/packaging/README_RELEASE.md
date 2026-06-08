# DWSBatchModelValidator 发布说明

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

## 输出

- `dist/DWSBatchModelValidator/DWSBatchModelValidator.exe`
- `dist/DWSBatchModelValidator.zip`
- 如果安装了 Inno Setup：`dist_installer/DWSBatchModelValidator_Setup_1.0.0.exe`

## 验收

```powershell
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --diagnose
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --window-smoke-test
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --cli --model models\yolo26s-seg.pt --images data\images --labels data\labels --device cpu
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --cli --model models\yolo26s-seg_openvino_model\yolo26s-seg.xml --images data\images --labels data\labels --device cpu
```
