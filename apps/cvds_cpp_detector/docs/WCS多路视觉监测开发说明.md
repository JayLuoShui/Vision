# WCS 多路视觉监测开发说明

当前源码保留 WCS 配置、消息和 TCP 发布能力，但构建目标仍是单一 `CVDS_Cpp_Detector.exe`。没有独立 WCS 监控程序，也没有 worker 进程链路。

## 当前代码边界

| 模块 | 当前作用 |
|---|---|
| `WcsConfig.*` | 描述 WCS endpoint、相机和多相机配置 |
| `WcsMessage.*` | 生成 WCS JSON 消息 |
| `WcsTcpClient.*` | TCP 连接、重连、队列和按行发送 JSON |
| `WcsPayloadPublisher.*` | 从检测流水线向 WCS 发布 payload |
| `VideoPipeline` | 每路视频检测、计数、堵包和输出 |
| `PipelineRuntimeManager` | 管理多路 `VideoPipeline` 线程 |

## 当前运行链路

```text
本地视频 / RTSP / 海康 RTSP
  -> VideoPipeline
  -> DetectorBackend(OpenVINO 或 TensorRT)
  -> ByteTrack
  -> FlowCounter
  -> JamDetector
  -> ResultWriter
  -> DashboardPayloadBuilder
  -> 可选 WcsPayloadPublisher
```

## WCS JSON 消息

当前保留以下消息类型：

- `HEARTBEAT`
- `CAMERA_STATUS`
- `FLOW_UPDATE`
- `JAM_ON`
- `JAM_OFF`
- `ERROR`

消息为 newline-delimited JSON，便于 WCS 按行解析。

## 后续开发约束

- 先复用当前 `VideoPipeline`，不要恢复 Python worker。
- 如果需要独立 WCS 程序，必须先明确新可执行目标，再改 CMake。
- 如果需要批量推理，应在 C++ 内扩展 TensorRT/OpenVINO 调度，不把 PT/ONNX worker 放回发布包。
