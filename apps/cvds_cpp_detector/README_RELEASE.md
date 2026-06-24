# CVDS_Cpp_Detector 发布说明

本发布包是单一 `CVDS_Cpp_Detector.exe`，采用纯 C++ OpenVINO Runtime；如果构建机安装了 TensorRT SDK，也可启用纯 C++ TensorRT GPU 推理。

## 发布包内容

- `CVDS_Cpp_Detector.exe`
- Qt、OpenCV、OpenVINO、TBB、可选 TensorRT 和 MSVC 运行库
- `models/` 中的 OpenVINO IR `.xml + .bin`
- `VERSION.txt`

发布包不需要安装 Python 或 conda，也不包含独立推理进程。

## 支持范围

- 模型：OpenVINO IR `.xml + .bin`；TensorRT `.engine/.plan`
- 设备：OpenVINO 为 `AUTO / CPU / GPU / NPU`，TensorRT 为 CUDA GPU
- 视频：本地视频文件或 RTSP 视频流

## 构建

```powershell
pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

输出：

```text
dist/CVDS_Cpp_Detector/CVDS_Cpp_Detector.exe
dist_installer/CVDS_Cpp_Detector_Setup_<version>.exe
```

## 运行

```powershell
.\dist\CVDS_Cpp_Detector\CVDS_Cpp_Detector.exe
```

程序输出名称保持不变：

- `cvds_online_parcel_flow_monitor.mp4`
- `flow_events.csv`
- `jam_signals.jsonl`
- `flow_summary.json`
- `cvds_preview.jpg`

堵包信号名称保持为 `IO_JAM_ON` 和 `IO_JAM_OFF`。
