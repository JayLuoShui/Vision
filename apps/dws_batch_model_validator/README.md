# DWS 批量模型检测验证工具

这是一个用于 DWS 顶视图包裹检测/计数的批量验证程序。它保留原有 YOLO segmentation 检测、DWS 判定和结果输出，同时新增 Windows 图形界面、环境自检、日志、打包和安装脚本。

## 功能

- 选择 `.pt` YOLO segmentation 模型，或选择 Ultralytics 导出的 OpenVINO `.xml` 模型。
- 选择图片目录、YOLO segmentation 标签目录和输出目录。
- 设置输入尺寸、`low_conf`、`high_conf`、`iou`。
- 选择自动 / CPU / GPU。
- 批量生成 `results.csv`、`summary.json`、`vis/` 和错误样本目录。
- GUI 实时显示进度、日志、结果摘要和可视化预览。
- CLI 仍可批处理，适合自动化验证。

## 判定规则

原有业务规则保持不变：

- `pred_count >= 2` -> `MULTI` -> `INTERCEPT`
- `pred_count == 1 且 suspect_count >= 1` -> `SUSPECT_MULTI` -> `INTERCEPT_REVIEW`
- `pred_count == 1` -> `SINGLE` -> `PASS`
- `pred_count == 0` -> `UNKNOWN` -> `REVIEW`

## 源码运行

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-gui.txt
.\venv\Scripts\python.exe run_gui.py
```

命令行批处理：

```powershell
.\venv\Scripts\python.exe run_batch.py --model models\yolo26s-seg.pt --images data\images --labels data\labels --imgsz 736 960 --device cpu --low-conf 0.25 --high-conf 0.55 --iou 0.50
```

OpenVINO 推理：

```powershell
.\venv\Scripts\python.exe run_batch.py --model models\yolo26s-seg_openvino_model\yolo26s-seg.xml --images data\images --labels data\labels --device cpu
```

环境自检：

```powershell
.\venv\Scripts\python.exe run_batch.py --diagnose
```

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

输出：

- `dist/DWSBatchModelValidator/DWSBatchModelValidator.exe`
- `dist/DWSBatchModelValidator.zip`
- 如果安装了 Inno Setup：`dist_installer/DWSBatchModelValidator_Setup_1.0.0.exe`

## 打包后运行

无参数双击：打开 GUI。

CLI：

```powershell
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --cli --model models\yolo26s-seg.pt --images data\images --labels data\labels --device cpu
```

诊断：

```powershell
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --diagnose
```

## 输出结构

```text
outputs/runs/yyyyMMdd_HHmmss/
  resolved_config.json
  results.csv
  summary.json
  failed_items.csv
  vis/
  errors/
    false_single/
    false_multi/
    unknown/
```

默认输出目录为：

```text
%LOCALAPPDATA%/CVDS/DWSBatchModelValidator/outputs/runs
```

## 测试

```powershell
pytest tests -q
```

当前测试覆盖：

- 判定逻辑。
- YOLO label 计数。
- 指标统计。
- 配置加载和诊断。

## 说明

CPU 模式是稳定保底方案。自动模式会优先 CUDA GPU，没有 CUDA 时回退 CPU。强制 GPU 但 CUDA 不可用时会显示中文错误，不会直接崩溃。OpenVINO 模型使用 CPU 方式运行，适合没有 CUDA 环境的 Windows 电脑。
