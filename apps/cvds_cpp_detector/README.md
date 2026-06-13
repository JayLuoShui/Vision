# CVDS 多区域包裹流量监控看板

这是 `CVDS_Qt_Platform` 的 C++/Qt 精简版，只保留现场视频检测和流量监测。

## 功能

- 不包含模型训练页。
- 不包含训练监控页。
- 不再提供 ONNX 模型检测入口。
- 使用 `.pt` 权重做视频检测，检测结果与 Ultralytics PT 推理保持同一条链路。
- 软件名为 `CVDS包裹流量检测工具`。
- “视觉模型”路径支持记忆上次选择的 `.pt` 模型。
- 视频源支持本地视频，也支持通过海康相机 RTSP 地址接入视频流。
- 支持新增、命名、删除、保存和加载多个多边形流量 ROI。
- 每个 ROI 可独立设置是否计数、是否判断堵包和堵包秒数。
- 可指定主统计区域；顶部累计数量只读取该区域，不把 T 型口各区域重复相加。
- 右侧视频首帧支持当前区域逐点绘制：右键或回车完成，Esc/Ctrl+Z 或按钮撤回上一个点。
- ROI 未右键或回车完成前，不会自动形成封闭区域。
- 界面改为更接近工业软件的深色钢灰配色，重点按钮用绿色/红色区分运行和停止。
- 类别和执行设备下拉栏显示下拉图标；数字输入框的增大/减小按钮分别为正三角形和倒三角形。
- 可选绘制多边形检测区域，只在指定区域内推理。
- 支持 ByteTrack 跟踪，并为每个 ROI 独立统计累计数量、区域内数量和最大区域内数量。
- 每个 ROI 独立判断堵包；任一区域堵包时，KPI、区域表和视频区域红色闪烁。
- 看板显示累计包裹、当前状态、区域内包裹、堵包次数和各区域停滞秒数。
- 堵包发生和解除会写入 `jam_signals.jsonl`，包含区域 ID、区域名称、`IO_JAM_ON` / `IO_JAM_OFF`。
- 输出带框视频、多区域事件 CSV、堵包 JSONL、多区域汇总 JSON 和界面预览图。
- 类别下拉框会按 PT 权重里的类别信息自动生成，不再写死 `parcel`。
- 默认使用自动设备；有 CUDA 时用 GPU，没有 CUDA 时用 CPU。手动选择 GPU 但不可用时，会给出中文错误。

## 目录

```text
apps/cvds_cpp_detector/
  CMakeLists.txt
  src/main.cpp
  src/MainWindow.h
  src/MainWindow.cpp
  src/RegionConfig.h
  src/RegionConfig.cpp
  src/RuntimePaths.h
  src/RuntimePaths.cpp
  configs/bytetrack.yaml
  configs/regions.example.json
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
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
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
  --regions .\configs\regions.example.json `
  --imgsz 960 `
  --device auto `
  --tracker .\dist\CVDS_Package_Flow_Detector\configs\bytetrack.yaml `
  --jam-signal-path "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs\jam_signals.jsonl"
```

旧命令仍可使用 `--roi ... --jam-seconds 5`，会自动转换为 `default` 区域。

## 使用说明

- 先选择视觉模型。
- 再选择本地视频源，或填写海康相机 IP、账号、密码和通道后点击“接入”。
- 点击“新增区域”，填写现场名称并选择该区域。
- 点击“绘制流量ROI”，在画面上左键逐点绘制当前区域。
- 画错时可以点击“撤回ROI点”，也可以在画面聚焦后按 Esc 或 Ctrl+Z。
- 右键画面或按回车结束当前 ROI 绘制。
- 按相同方式配置其他区域，并选择一个主统计区域。
- “参与累计”和“启用堵包”分别控制当前区域的计数和堵包判断。
- 点击“保存区域配置”后，配置写入 AppData；开始检测时同时写入输出目录的 `regions.json`。
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
.\.venv\Scripts\python.exe -m pytest .\tests\test_cvds_multi_roi_worker.py .\tests\test_cpp_detector_structure.py -q
.\.venv\Scripts\python.exe -m py_compile .\apps\cvds_cpp_detector\scripts\worker_entry.py .\apps\cvds_cpp_detector\scripts\pt_video_flow_monitor.py
cmake --build .\build\cvds_cpp_detector_release --config Release
```
