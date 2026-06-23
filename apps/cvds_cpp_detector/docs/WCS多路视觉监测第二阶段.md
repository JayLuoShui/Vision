# WCS 多路视觉监测第二阶段说明

本阶段在第一阶段的 WCS 配置、协议和 TCP 通信骨架基础上，继续补齐多路运行闭环。

## 新增可执行程序

新增独立程序：

```text
CVDS_WCS_Multi_Camera_Monitor
```

保留原有单路工具：

```text
CVDS_Cpp_Detector
```

这样可以避免多路 WCS 改造影响原有单路在线检测工具。

## 已完成能力

### 1. Qt 多路相机宫格

`WcsMonitorWindow` 提供 WCS 专用主界面：

- 加载 `configs/cameras.wcs.json` 或 `configs/cameras.wcs.example.json`；
- 根据启用相机数量自动生成 2x2 / 3x3 / 4x4 宫格；
- 每个相机 Tile 显示相机名、相机 ID、线路、皮带、状态、FPS、累计计数、区域内数量和堵包次数；
- 堵包状态下 Tile 红色高亮；
- 左侧表格汇总多路摄像头在线状态。

### 2. CameraWorker

新增 `CameraWorker`：

- 每路相机独立解码；
- 支持本地摄像头编号、视频文件、RTSP；
- 支持 RTSP TCP / UDP；
- 读取异常后按 `reconnect_seconds` 自动重连；
- 按 `target_fps` 限速，避免预览阶段占满 CPU；
- 上报 `CameraRuntimeSnapshot`。

### 3. WcsInferenceManager

新增 `WcsInferenceManager`：

- 面向多路 WCS 运行的推理调度层；
- 当前采用“每路相机一个 worker 进程”的保守实现，复用现有统一 worker；
- 为每路相机生成独立 `regions.json`、输出目录、预览图和堵包 JSONL；
- 解析 worker 输出的 `frame / regions / jam / done / error` payload；
- 按 `camera_id + roi_id` 聚合 dashboard payload；
- 将 ROI 统计转换为 `WcsFlowUpdate`；
- 将堵包发生 / 解除转换为 `WcsJamEvent`；
- 将运行状态转换为 `CameraRuntimeSnapshot`。

### 4. WCS 事件闭环

`WcsMonitorWindow` 已接入 `WcsTcpClient`：

- 启动监测时连接 WCS；
- 定时发送 `HEARTBEAT`；
- 摄像头状态变化发送 `CAMERA_STATUS`；
- ROI 流量更新发送 `FLOW_UPDATE`；
- 堵包发生发送 `JAM_ON`；
- 堵包解除发送 `JAM_OFF`；
- 推理错误发送 `ERROR`。

## 当前实现边界

当前第二阶段选择低风险演进路线：

```text
Qt WCS 多路界面
  -> WcsInferenceManager
  -> 每路相机独立 cvds_detector_worker 进程
  -> 现有 YOLO / ONNX / OpenVINO worker
  -> WCS TCP JSON
```

这已经可以完成多路接入、多路展示、多路事件上报和 WCS 侧闭环验证。

## 下一阶段建议

后续如需进一步提升 GPU 利用率，应将 `WcsInferenceManager` 从“多进程 worker”升级为真正的 GPU 批量推理引擎：

```text
CameraWorker 多路解码
  -> FrameQueue
  -> BatchScheduler
  -> TensorRT / ONNXRuntime-GPU InferenceEngine
  -> ByteTrack / FlowCounter / JamDetector
  -> WCS Event Dispatcher
```

优先事项：

1. TensorRT engine 直接 C++ 推理；
2. 多路帧队列和动态 batch；
3. 统一 ByteTrack 多路实例管理；
4. Qt Tile 上直接 ROI 编辑并写回 `cameras.wcs.json`；
5. GPU 使用率采集并填充 HEARTBEAT 的 `gpu_usage`。
