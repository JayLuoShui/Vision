# CVDS_Cpp_Detector 发布包说明

本目录是 `CVDS_Cpp_Detector` 的 Windows 便携发布包。程序为单一 Qt 桌面应用，运行端使用纯 C++ OpenVINO Runtime；如果构建时启用了 TensorRT，也可加载 TensorRT engine。

## 包内主要内容

- `CVDS_Cpp_Detector.exe`
- Qt、OpenCV、OpenVINO、TBB、MSVC 运行库
- 可选 `nvinfer_*.dll`
- `models/` 下的 OpenVINO IR `.xml + .bin`
- `VERSION.txt`
- `README_RELEASE.md`

发布包不需要 Python、conda、Torch、Ultralytics 或独立 worker 进程。

## 支持内容

| 类别 | 当前支持 |
|---|---|
| 模型 | OpenVINO IR `.xml + .bin`、TensorRT `.engine/.plan` |
| OpenVINO 设备 | `AUTO`、`CPU`、`GPU` |
| TensorRT 设备 | NVIDIA CUDA GPU 编号，例如 `0` |
| 视频源 | 本地视频、RTSP、海康 RTSP |
| 多路检测 | 多路本地/RTSP 源，或海康通道号列表 |
| 输出 | 每路独立生成视频、CSV、JSONL、summary 和预览图 |

## 使用方式

双击：

```text
CVDS_Cpp_Detector.exe
```

常规流程：

1. 选择视频源或填写海康参数。
2. 点击“应用本地视频”或“应用视频流”，让画面出现。
3. 绘制流量 ROI 和检测 ROI。
4. 选择模型、后端、设备和输出目录。
5. 点击“开始检测”。

## 输出文件

- `cvds_online_parcel_flow_monitor.mp4`
- `flow_events.csv`
- `jam_signals.jsonl`
- `flow_summary.json`
- `cvds_preview.jpg`

堵包信号固定为 `IO_JAM_ON` 和 `IO_JAM_OFF`。
