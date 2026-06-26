# CVDS 在线包裹流量监测

这是单一 `CVDS_Cpp_Detector` Windows 桌面程序，运行时采用纯 C++ OpenVINO Runtime，并可在安装 TensorRT SDK 的构建机上启用纯 C++ TensorRT GPU 推理，不需要 Python 环境或额外推理进程。

## 功能

- 使用 OpenCV 读取本地视频或 RTSP 视频流。
- 使用 OpenVINO 或 TensorRT 完成目标检测，使用 ByteTrack 完成跟踪。
- 支持多边形检测区域、多个流量区域、累计计数和堵包判断。
- 支持多路视频在线检测：海康视频流可在“多路通道”填写 `1,2,3` 自动生成多路 RTSP；也可在“多路视频源”中每行填写一路本地视频或 RTSP 地址。输出会写入 `camera_1`、`camera_2` 等子目录。
- OpenVINO 支持设备 `AUTO / CPU / GPU`；TensorRT 使用 NVIDIA CUDA GPU。
- 支持 OpenVINO IR `.xml + .bin`，以及已构建好的 TensorRT `.engine/.plan`。

## 输出文件

输出目录保持以下固定名称：

- `cvds_online_parcel_flow_monitor.mp4`
- `flow_events.csv`
- `jam_signals.jsonl`
- `flow_summary.json`
- `cvds_preview.jpg`

堵包发生和解除分别写入 `IO_JAM_ON`、`IO_JAM_OFF`。

## 构建

构建机需要 Visual Studio Build Tools 2022、CMake、Ninja、Qt 6、OpenCV、OpenVINO Runtime 和 Inno Setup。TensorRT 为可选 GPU 后端；需要时安装 CUDA、TensorRT SDK，并设置 `TENSORRT_ROOT`。

```powershell
$env:QT_DIR = "D:\Qt\6.x.x\msvc2022_64"
$env:OPENCV_DIR = "D:\opencv\build"
$env:OPENVINO_DIR = "C:\Program Files (x86)\Intel\openvino\runtime\cmake"
$env:TENSORRT_ROOT = "C:\TensorRT"

pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

只生成便携目录：

```powershell
pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1 -SkipInstaller
```

默认输出：

```text
dist/CVDS_Cpp_Detector/CVDS_Cpp_Detector.exe
dist_installer/CVDS_Cpp_Detector_Setup_<version>.exe
```

## 运行

```powershell
.\dist\CVDS_Cpp_Detector\CVDS_Cpp_Detector.exe
```

在界面中选择推理后端。OpenVINO 使用 `.xml` 文件或模型目录，同目录必须存在同名 `.bin`；TensorRT 使用已构建好的 `.engine/.plan`。单路检测选择一个视频源即可；海康多路检测在“多路通道”里填写通道号，例如 `1,2,3`；其它多路检测可在“多路视频源”里每行填写一路本地视频或 RTSP 地址，然后选择输出目录和设备并开始检测。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests\test_cpp_detector_structure.py -q
cmake -S .\apps\cvds_cpp_detector -B .\build\cvds_cpp_detector_release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build .\build\cvds_cpp_detector_release --target CVDS_Cpp_Detector
```
