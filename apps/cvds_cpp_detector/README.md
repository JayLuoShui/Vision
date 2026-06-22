# CVDS 在线包裹流量监测

这是面向输送线现场的 C++/Qt 在线包裹流量监测软件。

## 功能

- 不包含模型训练页。
- 不包含训练监控页。
- 推理参数统一支持 PT、ONNX、OpenVINO 模型。
- 软件名为 `CVDS在线包裹流量监测`，英文为 `CVDS ONLINE PARCEL FLOW MONITOR`。
- “视觉模型”位于推理参数栏，支持模型文件和 OpenVINO 模型目录。
- 视频源只分为本地文件与视频流。
- 海康视频流支持 IP、RTSP 端口、账号、密码、通道、主/子码流及 TCP/UDP 设置。
- 海康连接测试由独立 worker 异步执行，不阻塞主界面。
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
- 类别下拉框会按模型元数据自动生成，不再写死 `parcel`。
- 推理设备按模型格式校验；显式选择不可用的设备会直接报错。

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
  --model .\weights\cvds_yolo26n_package_best.pt `
  --source .\sample.mp4 `
  --rtsp-transport tcp `
  --output-dir "$env:LOCALAPPDATA\CVDS\CVDS在线包裹流量监测\runs" `
  --preview-path "$env:LOCALAPPDATA\CVDS\CVDS在线包裹流量监测\runs\preview.jpg" `
  --regions .\configs\regions.example.json `
  --imgsz 960 `
  --device auto `
  --tracker .\dist\CVDS_Package_Flow_Detector\configs\bytetrack.yaml `
  --jam-signal-path "$env:LOCALAPPDATA\CVDS\CVDS在线包裹流量监测\runs\jam_signals.jsonl"
```

旧命令仍可使用 `--roi ... --jam-seconds 5`，会自动转换为 `default` 区域。

## 使用说明

- 在“推理参数”选择 PT、ONNX、OpenVINO 模型。
- 在“视频源”选择本地文件，或配置海康设备后点击“测试连接”和“应用视频流”。
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
  - `cvds_online_parcel_flow_monitor.mp4`
  - `flow_events.csv`
  - `jam_signals.jsonl`
  - `flow_summary.json`
  - `cvds_preview.jpg`

## 搜索记录

- 海康官方 RTSP 规则：`rtsp://设备地址:端口/Streaming/Channels/通道号与码流号`，通道 1 主码流为 `101`、子码流为 `102`。来源：https://supportusa.hikvision.com/support/solutions/articles/17000129064-how-do-i-get-my-rtsp-stream-
- 海康也提供 Device Network SDK，但 Windows 运行包较大，当前软件采用标准 RTSP/ISAPI 接口，减少专有 DLL 和部署约束。来源：https://www.hikvision.com/us-en/support/download/sdk/device-network-sdk--for-windows-64-bit-/
- Ultralytics 官方支持加载 ONNX 和 OpenVINO 导出模型进行预测。来源：https://docs.ultralytics.com/integrations/onnx 和 https://docs.ultralytics.com/integrations/openvino

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests\test_cvds_multi_roi_worker.py .\tests\test_cpp_detector_structure.py -q
.\.venv\Scripts\python.exe -m py_compile .\apps\cvds_cpp_detector\scripts\worker_entry.py .\apps\cvds_cpp_detector\scripts\pt_video_flow_monitor.py
cmake --build .\build\cvds_cpp_detector_release --config Release
```
