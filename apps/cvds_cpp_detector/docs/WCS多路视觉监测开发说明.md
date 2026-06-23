# WCS 端多路视觉流量监测开发说明

本模块用于将 `apps/cvds_cpp_detector` 从单路视频流量检测工具升级为 WCS 端多路摄像头视觉流量监测系统。目标运行环境为带 NVIDIA GPU 的 Windows 工控机。

## 目标架构

```text
多路 RTSP / 工业相机
  -> CameraWorker 解码与重连
  -> GPU InferenceManager 批量推理
  -> ByteTrack / ROI FlowCounter
  -> JamDetector
  -> WcsTcpClient TCP JSON 上报
  -> Qt 多画面监控、ROI 配置、日志与报警界面
```

当前提交先落地配置模型与 WCS TCP JSON 通信骨架，后续再将现有单 worker 调度替换为多 worker/多相机调度。

## 配置文件

示例：`configs/cameras.wcs.example.json`

核心字段：

- `inference.backend`: `tensorrt`、`onnxruntime-gpu` 或 `pytorch-cuda`。
- `inference.device`: NVIDIA GPU 编号，通常为 `0`。
- `wcs.host` / `wcs.port`: WCS TCP 服务端地址。
- `cameras[].camera_id`: 全局唯一相机编号。
- `cameras[].line_id`: 现场线体编号。
- `cameras[].belt_id`: 皮带或合流口编号。
- `cameras[].source`: RTSP 地址或工业相机输入标识。
- `cameras[].regions`: 当前相机的流量 ROI 和堵包 ROI。

## TCP JSON 协议

默认采用 newline-delimited JSON，每条消息以 `\n` 结束，便于 WCS 按行解析。

### 心跳

```json
{
  "msg_type": "HEARTBEAT",
  "device_id": "VISION_IPC_01",
  "timestamp": "2026-06-23T18:00:00.000Z",
  "camera_online": 8,
  "camera_total": 8,
  "gpu_usage": 64.5
}
```

### 摄像头状态

```json
{
  "msg_type": "CAMERA_STATUS",
  "device_id": "VISION_IPC_01",
  "timestamp": "2026-06-23T18:00:00.000Z",
  "camera_id": "CAM_TJ_001",
  "line_id": "LINE_A",
  "belt_id": "BELT_T_01",
  "status": "ONLINE",
  "decode_fps": 25.0,
  "infer_fps": 12.0,
  "dropped_frames": 0,
  "jam_active": false,
  "total_count": 15234,
  "inside_count": 2,
  "jam_count": 0
}
```

### 流量上报

```json
{
  "msg_type": "FLOW_UPDATE",
  "device_id": "VISION_IPC_01",
  "timestamp": "2026-06-23T18:00:00.000Z",
  "camera_id": "CAM_TJ_001",
  "line_id": "LINE_A",
  "belt_id": "BELT_T_01",
  "roi_id": "T_JUNCTION_MAIN",
  "roi_name": "主线交汇口",
  "count_total": 15234,
  "count_last_minute": 126,
  "inside_count": 2,
  "fps": 12.0
}
```

### 堵包发生

```json
{
  "msg_type": "JAM_ON",
  "device_id": "VISION_IPC_01",
  "timestamp": "2026-06-23T18:00:00.000Z",
  "camera_id": "CAM_TJ_001",
  "line_id": "LINE_A",
  "belt_id": "BELT_T_01",
  "roi_id": "T_JUNCTION_MAIN",
  "roi_name": "主线交汇口",
  "jam_confidence": 0.92,
  "object_count": 8,
  "avg_speed": 0.03,
  "stay_time_max": 7.4,
  "flow_count_window": 0,
  "snapshot": "alarm_images/CAM_TJ_001_20260623_180000.jpg"
}
```

### 堵包解除

```json
{
  "msg_type": "JAM_OFF",
  "device_id": "VISION_IPC_01",
  "timestamp": "2026-06-23T18:00:12.000Z",
  "camera_id": "CAM_TJ_001",
  "line_id": "LINE_A",
  "belt_id": "BELT_T_01",
  "roi_id": "T_JUNCTION_MAIN",
  "roi_name": "主线交汇口",
  "duration_seconds": 12.0,
  "snapshot": "alarm_images/CAM_TJ_001_20260623_180000.jpg"
}
```

## 后续集成步骤

1. 在 `MainWindow` 增加“WCS 配置”和“摄像头列表”页，加载 `MultiCameraSystemConfig`。
2. 用 `CameraWorker` 替换单 `VideoPreviewWorker`，每路相机独立解码、重连、预览。
3. 用 `InferenceManager` 管理 GPU 批量推理，支持 TensorRT FP16/INT8、ONNXRuntime-GPU 和 PyTorch CUDA。
4. 将现有 worker 输出的 dashboard JSON 扩展为按 `camera_id + roi_id` 聚合。
5. 将 `RegionRuntimeState` 转换为 `WcsFlowUpdate` / `WcsJamEvent`，通过 `WcsTcpClient` 上报。
6. Qt 界面增加 2x2/3x3/4x4 多画面预览、相机在线状态、报警过滤和日志查询。

## 堵包判定建议

现场 WCS 联动不应只使用“流量不更新”。推荐使用融合条件：

```text
jam = ROI 内有包裹
   && 平均速度低于阈值
   && 最大停留时间超过阈值
   && 最近窗口通过数量为 0 或明显下降
   && 区域目标数量 / 占用率超过阈值
```

WCS 只接收已去抖的 `JAM_ON` / `JAM_OFF`，避免相机画面抖动或短暂停顿导致频繁报警。
