# CVDS 在线包裹流量监测

`CVDS_Cpp_Detector` 是一个 Windows Qt 桌面程序，用于本地视频或 RTSP 视频流的包裹检测、跟踪、计数和堵包告警。当前运行端是纯 C++：Qt + OpenCV + OpenVINO Runtime，可选 TensorRT。

## 当前能力

- 读取本地视频文件、普通 RTSP 地址和海康 RTSP 视频流。
- 支持单路或多路视频源；多路结果写入 `camera_1`、`camera_2` 等子目录。
- 支持 OpenVINO IR `.xml + .bin` 或模型目录。
- 构建机具备 CUDA + TensorRT SDK 时，可加载 TensorRT `.engine/.plan`。
- 使用 C++ ByteTrack 做目标跟踪。
- 支持多个流量 ROI、检测 ROI、主统计区域、区域表和顶部 KPI。
- 支持堵包检测，堵包发生写 `IO_JAM_ON`，解除写 `IO_JAM_OFF`。
- 支持 WCS TCP JSON 上报配置和消息模块，当前由同一个 `CVDS_Cpp_Detector` 程序承载。

不在当前运行端内的内容：Python worker、PyInstaller、PT/ONNX 直接推理、独立 WCS 可执行程序。

## 目录结构

| 路径 | 作用 |
|---|---|
| `src/MainWindow.*` | Qt 主界面、视频源配置、ROI 编辑、KPI、日志和多路画面合成 |
| `src/pipeline/VideoPipeline.*` | 单路检测流水线：读帧、推理、跟踪、计数、堵包、输出 |
| `src/pipeline/PipelineRuntimeManager.*` | 多路检测线程管理 |
| `src/inference/*` | OpenVINO、TensorRT 和 YOLO 后处理 |
| `src/tracking/*` | ByteTrack、Kalman 和匈牙利匹配 |
| `src/RegionConfig.*` | ROI 配置读写和校验 |
| `src/Wcs*`、`src/pipeline/WcsPayloadPublisher.*` | WCS 配置、消息和 TCP 发布 |
| `configs/*.json` | ROI、WCS 和相机示例配置 |
| `packaging/build_release.ps1` | Windows Release 构建和打包脚本 |

## 输出文件

每路输出目录包含：

- `cvds_online_parcel_flow_monitor.mp4`
- `flow_events.csv`
- `jam_signals.jsonl`
- `flow_summary.json`
- `cvds_preview.jpg`

多路检测时，外层输出目录下会生成 `camera_1`、`camera_2` 等子目录。

## 构建

需要 Visual Studio Build Tools 2022、CMake、Ninja、Qt 6、OpenCV、OpenVINO Runtime 和 Inno Setup。TensorRT 是可选后端，需要 CUDA 和 TensorRT SDK。

```powershell
$env:QT_DIR = "C:\Qt\6.9.3\msvc2022_64"
$env:OPENCV_DIR = "C:\tools\opencv\build"
$env:OPENVINO_DIR = "D:\Demo\Vision\.venv\Lib\site-packages\openvino\cmake"
$env:TENSORRT_ROOT = "D:\tools\TensorRT-11.0.0.114"

pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

不覆盖已有发布包时，使用独立 `DistName`：

```powershell
pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1 `
  -DistName CVDS_Cpp_Detector_TestBuild `
  -SkipInstaller
```

## 运行

```powershell
.\dist\CVDS_Cpp_Detector\CVDS_Cpp_Detector.exe
```

界面中选择后端：

- OpenVINO：选择 `.xml` 文件或只包含一个 `.xml` 的模型目录，同目录必须有同名 `.bin`。
- OpenVINO 设备：AUTO / CPU / GPU。
- TensorRT：选择已构建好的 `.engine/.plan`。

本地多路视频在“多路视频源”中每行填一路；海康多路视频在“多路通道”中填写 `1,2,3`。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests\test_cpp_detector_structure.py -q
.\.venv\Scripts\python.exe -m ruff check .\tests\test_cpp_detector_structure.py
cmake --build .\build\CVDS_Cpp_Detector_TestBuild\cpp --config Release --target CVDS_Cpp_Detector
```
