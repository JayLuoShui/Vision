# 当前任务清单

## 已完成

- [x] 单一 `CVDS_Cpp_Detector.exe` 纯 C++ 运行端。
- [x] OpenVINO IR 推理后端。
- [x] TensorRT engine 推理后端。
- [x] C++ ByteTrack 跟踪。
- [x] 多 ROI 计数、主统计区域和区域状态表。
- [x] 堵包检测、红色告警和 `IO_JAM_ON / IO_JAM_OFF` 输出。
- [x] 本地视频、普通 RTSP 和海康 RTSP。
- [x] 多路视频检测和多画面合成。
- [x] WCS 配置、消息和 TCP 发布模块。
- [x] Release 打包脚本拦截旧 Python/worker 运行端残留。

## 当前维护重点

- [ ] 文档必须以当前 CMake 和发布包为准。
- [ ] 测试必须覆盖 `PipelineRuntimeManager` 当前架构。
- [ ] 发布包不能覆盖用户已有正式包，除非明确指定同名 `DistName`。

## 不属于当前运行端

- Python worker。
- PyInstaller。
- PT/ONNX 直接推理。
- 独立 `CVDS_WCS_Multi_Camera_Monitor.exe`。
