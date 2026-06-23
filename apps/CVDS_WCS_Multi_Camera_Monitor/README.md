# CVDS WCS 多路摄像头视觉流量监测系统

该目录是 WCS 端多路摄像头视觉监测程序的独立应用入口。

## 目标定位

系统运行在带 NVIDIA GPU 的工控机上，面向 WCS 端多路摄像头监控，完成：

- 多路 RTSP / 工业相机视频接入；
- GPU 模型推理调度；
- ROI 流量统计；
- 堵包发生 / 解除检测；
- Qt 多画面宫格预览；
- TCP JSON 协议向 WCS 上报 HEARTBEAT、CAMERA_STATUS、FLOW_UPDATE、JAM_ON、JAM_OFF、ERROR。

## 当前实现说明

当前阶段采用过渡兼容层：

```text
apps/CVDS_WCS_Multi_Camera_Monitor
  -> 独立 CMake / configs / scripts / models
  -> 复用 apps/cvds_cpp_detector 中已实现的 WCS Qt 与 worker 调度代码
```

这样可以先形成独立应用目录，避免继续把 WCS 多路程序混在单路 `cvds_cpp_detector` 目录中。

## 后续重构方向

后续逐步将桥接文件替换为原生实现：

- `WcsMonitorWindow` -> `MainWindow`
- `WcsInferenceManager` -> `InferenceManager`
- worker 进程调度 -> C++ TensorRT / ONNXRuntime-GPU batch 推理
- 配置读取 -> `ConfigManager`
- ROI 编辑 -> `RoiEditor`
- 流量统计 -> `FlowCounter`
- 堵包判断 -> `JamDetector`
- WCS TCP 客户端 -> `WcsClient`
