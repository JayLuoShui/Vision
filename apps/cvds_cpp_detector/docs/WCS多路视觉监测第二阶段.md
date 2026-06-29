# WCS 多路视觉监测现状

这份文档原本记录 WCS 第二阶段方案。按当前源码整理后，结论如下。

## 已保留

- WCS 配置结构。
- WCS JSON 消息结构。
- WCS TCP 客户端。
- 多路 `VideoPipeline` 管理。
- 多路相机的 KPI 聚合和区域状态。

## 已变化

| 旧说法 | 当前事实 |
|---|---|
| 新增 `CVDS_WCS_Multi_Camera_Monitor` | 当前 CMake 只构建 `CVDS_Cpp_Detector` |
| 每路相机一个 worker 进程 | 当前是 C++ `VideoPipeline` 在线程中运行 |
| ONNXRuntime-GPU / PyTorch CUDA worker | 当前运行端只支持 OpenVINO 和可选 TensorRT |
| worker payload 聚合 | 当前由 C++ pipeline 构造 dashboard payload |

## 当前闭环

```text
多路视频源
  -> PipelineRuntimeManager
  -> 多个 VideoPipeline
  -> C++ 推理 / 跟踪 / 计数 / 堵包
  -> 主界面聚合显示
  -> 可选 WCS TCP JSON 发布
```

## 后续如果继续做 WCS

下一步应直接基于当前 C++ 管线扩展：

1. 明确是否真的需要独立 WCS 可执行程序。
2. 如果需要，先新增 CMake target。
3. 复用 `VideoPipeline`、`PipelineRuntimeManager`、`WcsTcpClient`。
4. 不恢复 Python worker。
