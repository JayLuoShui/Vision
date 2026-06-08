# CVDS PT 视频流量监测工具

这是 `CVDS_Qt_Platform` 的 C++/Qt 精简版，只保留现场视频检测和流量监测。

## 功能

- 不包含模型训练页。
- 不包含训练监控页。
- 不再提供 ONNX 模型检测入口。
- 使用 `.pt` 权重做视频检测，检测结果与 Ultralytics PT 推理保持同一条链路。
- 软件名为 `CVDS包裹流量检测工具`。
- “视觉模型”路径支持记忆上次选择的 `.pt` 模型。
- 视频源支持本地视频，也支持通过海康相机 RTSP 地址接入视频流。
- 右侧视频首帧支持多边形流量 ROI：左键逐点绘制，右键或回车完成，Esc/Ctrl+Z 或按钮撤回上一个点。
- ROI 未右键或回车完成前，不会自动形成封闭区域。
- 界面改为更接近工业软件的深色钢灰配色，重点按钮用绿色/红色区分运行和停止。
- 类别和执行设备下拉栏显示下拉图标；数字输入框的增大/减小按钮分别为正三角形和倒三角形。
- 可选绘制多边形检测区域，只在指定区域内推理。
- 支持 ByteTrack 跟踪并统计进入 ROI 的包裹流量。
- 当 ROI 内有包裹但流量数连续指定秒数不更新时，判定为堵包。
- 堵包发生和解除会写入 `jam_signals.jsonl`，字段里包含 `IO_JAM_ON` / `IO_JAM_OFF` 信号。
- 输出带框视频、流量事件 CSV、统计 JSON 和界面预览图。
- 类别下拉框会按 PT 权重里的类别信息自动生成，不再写死 `parcel`。
- 默认使用自动设备；有 CUDA 时用 GPU，没有 CUDA 时用 CPU。手动选择 GPU 但不可用时，会给出中文错误。

## 目录

```text
apps/cvds_cpp_detector/
  CMakeLists.txt
  src/main.cpp
  src/MainWindow.h
  src/MainWindow.cpp
  src/RuntimePaths.h
  src/RuntimePaths.cpp
  configs/bytetrack.yaml
  scripts/worker_entry.py
  scripts/inspect_model_metadata.py
  scripts/pt_video_flow_monitor.py
```

## 依赖

开发构建机需要：

- CMake
- Visual Studio Build Tools 2022
- Ninja
- Qt 6 msvc 64 位开发包
- OpenCV C++ 开发包
- Inno Setup

终端用户不需要安装 Python、Qt、OpenCV 或 conda。

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

输出：

```text
dist/CVDS_Package_Flow_Detector/
dist_installer/CVDS_Package_Flow_Detector_Setup_<version>.exe
```

## worker 命令示例

```powershell
.\dist\CVDS_Package_Flow_Detector\runtime\cvds_detector_worker.exe diagnose

.\dist\CVDS_Package_Flow_Detector\runtime\cvds_detector_worker.exe detect `
  --weights .\weights\cvds_yolo26n_package_best.pt `
  --source .\sample.mp4 `
  --output-dir "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs" `
  --preview-path "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs\preview.jpg" `
  --roi 0,0,639,0,639,359,0,359 `
  --imgsz 960 `
  --device auto `
  --tracker .\dist\CVDS_Package_Flow_Detector\configs\bytetrack.yaml `
  --jam-seconds 5 `
  --jam-signal-path "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs\jam_signals.jsonl"
```

## 使用说明

- 先选择视觉模型。
- 再选择本地视频源，或填写海康相机 IP、账号、密码和通道后点击“接入”。
- 点击“绘制流量ROI”，在画面上左键逐点画出需要统计流量的多边形区域。
- 画错时可以点击“撤回ROI点”，也可以在画面聚焦后按 Esc 或 Ctrl+Z。
- 右键画面或按回车结束当前 ROI 绘制。
- “检测区域”是可选项；设置后只在该区域检测，适合排除无关背景。
- “堵包判定秒”表示 ROI 内有包裹但流量数不更新多久后报警。
- 点击“开始检测”后，程序会输出：
  - `pt_video_flow_monitor.mp4`
  - `flow_events.csv`
  - `jam_signals.jsonl`
  - `flow_summary.json`
  - `cvds_pt_preview.jpg`

## 验证

```powershell
.\.venv\Scripts\python.exe .\tests\test_cpp_detector_structure.py
.\.venv\Scripts\python.exe -m py_compile .\apps\cvds_cpp_detector\scripts\worker_entry.py .\apps\cvds_cpp_detector\scripts\pt_video_flow_monitor.py
```
