# CVDS WCS 多路摄像头视觉流量监测系统

该目录是 WCS 端多路摄像头视觉监测程序的独立应用入口，目标版本为纯 C++ OpenVINO Runtime 版。

## 运行端模型格式

运行端只支持 OpenVINO IR：

- `.xml + .bin`
- 包含 `.xml` / `.bin` 的 OpenVINO 模型目录

其他训练阶段模型格式不作为本程序运行端输入。

## 已落地内容

- 独立 CMake 工程链接 `openvino::runtime`；
- 运行资源复制不再包含脚本式推理入口；
- OpenVINO Runtime C++ 加载入口；
- OpenCV C++ 视频读取、画框、预览图和视频输出框架；
- C++ 跟踪、ROI 流量统计、堵包判定和兼容输出文件框架；
- Qt6 Widgets 多画面宫格和 WCS TCP 事件上报入口。

## 输出文件

每路摄像头在运行目录下保持原文件名兼容：

```text
cvds_online_parcel_flow_monitor.mp4
flow_events.csv
jam_signals.jsonl
flow_summary.json
cvds_preview.jpg
```

`jam_signals.jsonl` 中继续输出 `IO_JAM_ON` 和 `IO_JAM_OFF`。

## 构建示例

```powershell
cmake -S .\apps\CVDS_WCS_Multi_Camera_Monitor -B .\build\wcs_openvino -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="%QT_DIR%;%OPENCV_DIR%;%OPENVINO_DIR%"
cmake --build .\build\wcs_openvino --config Release --target CVDS_WCS_Multi_Camera_Monitor
```

## 运行配置

复制并修改 `configs/cameras.json`、`configs/wcs.json`、`configs/runtime.json`。其中 `inference.model_path` 必须指向 OpenVINO `.xml` 文件或模型目录，`inference.device` 支持 `AUTO`、`CPU`、`GPU`、`NPU`。

## 未完成项

当前提交已完成纯 C++ OpenVINO 目录结构和运行框架，但仍需要继续补齐完整 YOLO 输出解析、低速停滞辅助堵包条件，以及将 `InferenceManager` 从临时调度实现切换为完整多路 `VideoPipeline` 线程调度。
