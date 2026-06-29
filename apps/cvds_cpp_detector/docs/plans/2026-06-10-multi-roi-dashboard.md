# 多 ROI 看板实现记录

这份文件保留为历史计划的收口记录。当前源码已经不是 Python worker 架构，而是纯 C++ 管线。

## 当前实现

| 能力 | 当前实现位置 |
|---|---|
| ROI 配置读写 | `src/RegionConfig.*` |
| ROI 绘制 | `RoiPreviewLabel` in `src/MainWindow.*` |
| 多路运行 | `src/pipeline/PipelineRuntimeManager.*` |
| 单路检测流水线 | `src/pipeline/VideoPipeline.*` |
| 计数 | `src/pipeline/FlowCounter.*` |
| 堵包 | `src/pipeline/JamDetector.*` |
| 输出文件 | `src/pipeline/ResultWriter.*` |
| 看板 payload | `src/pipeline/DashboardPayloadBuilder.*` |

## 已完成

- 多 ROI 区域配置。
- 主统计区域和多区域汇总。
- 区域表和顶部 KPI。
- 堵包红色闪烁。
- 多路视频 ROI 归属。
- 多路相机输出目录。
- OpenVINO / TensorRT 原生推理。

## 当前验证

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests\test_cpp_detector_structure.py -q
```

当前结构测试按 `PipelineRuntimeManager` 架构检查，不再检查旧 worker 参数。
