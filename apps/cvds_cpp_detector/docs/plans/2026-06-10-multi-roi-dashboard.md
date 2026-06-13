# CVDS Multi-ROI Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `apps/cvds_cpp_detector` 从单 ROI 流量工具升级为支持多 ROI 配置、分区计数、分区堵包和实时看板的桌面软件。

**Architecture:** 保留 Qt GUI 启动独立 Python worker 的现有结构。Python worker 负责读取 `regions.json`、跟踪、统计、堵包和结构化输出；Qt 负责区域编辑、配置保存、KPI、区域状态表和闪烁告警。旧 `--roi` 命令继续可用，但 Qt 新流程统一生成并传入 `--regions`。

**Tech Stack:** C++17、Qt 6 Widgets、OpenCV C++、Python 3、Ultralytics、OpenCV Python、pytest、CMake/Ninja、PyInstaller。

**Status:** 2026-06-11 已完成。全项目测试 80/80 通过，C++ Release 构建、GUI 冒烟和独立 worker 打包验证通过。

---

### Task 1: Worker 多 ROI 纯逻辑

**Files:**
- Modify: `apps/cvds_cpp_detector/scripts/pt_video_flow_monitor.py`
- Create: `tests/test_cvds_multi_roi_worker.py`

- [ ] 先写配置解析、旧 ROI 转换、多区域计数、主区域总数、堵包触发和解除测试。
- [ ] 运行 `.\.venv\Scripts\python.exe -m pytest tests\test_cvds_multi_roi_worker.py -q`，确认测试因函数缺失而失败。
- [ ] 新增 `FlowRegion`、`RegionState`、`load_regions()`、`build_single_region_from_legacy_roi()`、`update_region_counts()`、`update_region_jam_states()`、`build_frame_payload()`、`build_done_payload()`。
- [ ] 非法配置直接抛出明确错误：空区域、重复 ID、少于 3 个点、主统计区域不存在、堵包秒数小于 1。
- [ ] 再运行单文件测试，确认全部通过。

### Task 2: Worker 运行链路和兼容参数

**Files:**
- Modify: `apps/cvds_cpp_detector/scripts/pt_video_flow_monitor.py`
- Modify: `apps/cvds_cpp_detector/scripts/worker_entry.py`
- Modify: `tests/test_cvds_multi_roi_worker.py`

- [ ] 先写 `--regions` 优先、旧 `--roi` 兼容、frame/jam/done 输出字段和 CSV 区域字段测试。
- [ ] 运行测试，确认新协议测试失败。
- [ ] worker 入口允许 `--regions` 或 `--roi` 二选一，二者都没有时直接报错。
- [ ] 每个 ROI 独立维护 `flow_count`、`inside_count`、`max_inside_count`、`jam_count`；顶部总数只读取 `total_count_region`。
- [ ] frame 输出 `total_count`、`global_status`、`jam_active`、`regions`，同时保留旧单 ROI 字段。
- [ ] jam 输出统一为 `type=jam`，用 `event_type` 区分触发和解除，并包含区域 ID、名称和 IO 信号。
- [ ] CSV、JSONL、summary JSON 增加区域字段和区域汇总。
- [ ] 多 ROI 画面显示区域边界、名称、数量、状态；任一区域堵包时增加闪烁红色遮罩。
- [ ] 运行单文件测试和 Python 编译检查。

### Task 3: Qt 区域配置模型和编辑器

**Files:**
- Create: `apps/cvds_cpp_detector/src/RegionConfig.h`
- Create: `apps/cvds_cpp_detector/src/RegionConfig.cpp`
- Modify: `apps/cvds_cpp_detector/src/MainWindow.h`
- Modify: `apps/cvds_cpp_detector/src/MainWindow.cpp`
- Modify: `apps/cvds_cpp_detector/src/RuntimePaths.h`
- Modify: `apps/cvds_cpp_detector/src/RuntimePaths.cpp`
- Modify: `apps/cvds_cpp_detector/CMakeLists.txt`
- Modify: `tests/test_cpp_detector_structure.py`

- [ ] 先在结构测试中声明多 ROI 数据结构、JSON 保存/加载、区域操作按钮、主统计区域和 `--regions` 参数要求。
- [ ] 运行结构测试，确认新增断言失败。
- [ ] 新增 `RegionConfig`、`RegionRuntimeState` 和严格 JSON 读写函数。
- [ ] `RoiPreviewLabel` 支持多个区域、当前区域高亮、区域名称显示和独立多边形编辑；检测 ROI 保持原行为。
- [ ] 增加区域表、添加、重命名、删除、绘制、撤回、清空、保存、加载和主统计区域选择。
- [ ] 配置默认保存到 AppData `configs/regions.json`，检测启动前同步写入输出目录 `regions.json`。
- [ ] Qt 启动 worker 时传 `--regions`，不再依赖 GUI 单 ROI 文本参数。
- [ ] 构建前运行结构测试，确认通过。

### Task 4: Qt 看板和告警

**Files:**
- Modify: `apps/cvds_cpp_detector/src/MainWindow.h`
- Modify: `apps/cvds_cpp_detector/src/MainWindow.cpp`
- Modify: `tests/test_cpp_detector_structure.py`

- [ ] 先增加 KPI、区域状态表、dashboard 状态信号和闪烁计时器的结构测试。
- [ ] 运行结构测试，确认新增断言失败。
- [ ] DetectionWorker 解析 frame/jam/done 多区域 JSON，并发送 `dashboardStateReady`。
- [ ] 主窗口显示累计包裹、当前状态、区域内包裹、堵包次数和区域状态表。
- [ ] 任一区域堵包时，顶部、视频边框和对应表格行按 500ms 闪烁；解除后立即恢复。
- [ ] 日志显示区域名称、触发/解除、停滞秒数和 IO 信号。
- [ ] 运行结构测试并完成 C++ 构建。

### Task 5: 示例、发布和文档

**Files:**
- Create: `apps/cvds_cpp_detector/configs/regions.example.json`
- Modify: `packaging/build_release.ps1`
- Modify: `apps/cvds_cpp_detector/README.md`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `CONTEXT.md`

- [ ] 先扩展结构测试，要求示例配置存在且发布脚本校验它。
- [ ] 加入 ZIP 提供的三 ROI 示例配置。
- [ ] CMake 和发布脚本将 JSON 示例复制到发布包，并加入必需文件检查。
- [ ] 更新运行方式、输出协议、已完成功能和模块职责。
- [ ] 更新 `CONTEXT.md`，只记录本次状态、关键决定和验证结果。

### Task 6: 最终验证与 Review

**Files:**
- Review all changed files.

- [ ] 运行 `.\.venv\Scripts\python.exe -m pytest tests\test_cvds_multi_roi_worker.py tests\test_cpp_detector_structure.py -q`。
- [ ] 运行 `.\.venv\Scripts\python.exe -m py_compile apps\cvds_cpp_detector\scripts\worker_entry.py apps\cvds_cpp_detector\scripts\pt_video_flow_monitor.py`。
- [ ] 运行 Ruff 检查改动的 Python 文件。
- [ ] 使用现有 Qt/OpenCV 配置执行 CMake 配置和构建。
- [ ] Review 查 Bug：检查参数兼容、主统计区域、重复计数、堵包解除、JSON 字段和线程信号。
- [ ] 第一性原理复盘：删除不必要状态和重复实现，确认没有降级、兜底或静默失败。
