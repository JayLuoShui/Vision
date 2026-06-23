# CVDS WCS 多路摄像头视觉流量监测系统

该目录是 WCS 端多路摄像头视觉监测程序的独立应用入口，目标版本为纯 C++ OpenVINO Runtime 版。

## 运行端模型格式

运行端只支持 OpenVINO IR：

- `.xml + .bin`
- 包含 `.xml` / `.bin` 的 OpenVINO 模型目录

其他训练阶段模型格式不作为本程序运行端输入。

## 能力范围

- 多路本地视频 / RTSP 视频接入；
- OpenVINO Runtime C++ API 推理；
- OpenCV C++ 预处理、画框、预览图和视频输出；
- C++ 检测后处理、跟踪、ROI 流量统计和堵包判定；
- Qt6 Widgets 多画面宫格预览；
- TCP JSON 协议向 WCS 上报事件。

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
