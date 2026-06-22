# 项目结构说明

## 核心文件

- `CONTEXT.md`：记录当前进度、上次停靠点和关键决定。
- `README.md`：说明项目用途、运行方法、测试方法、搜索记录和待办事项。
- `scripts/prepare_cvds_package_roboflow_yolo26.py`：合并 Roboflow 包裹数据，清洗类别，生成 YOLO26 数据集，并做光照增强。
- `scripts/train_yolo26n_package.py`：以 YOLO26n 为骨干训练包裹检测模型。
- `scripts/training_monitor.py`：读取训练目录中的参数、指标、权重文件和训练进程状态，供 GUI 监控页使用。
- `scripts/track_count_packages.py`：对视频或相机流做包裹检测、ByteTrack 跟踪和过线/ROI 计数。
- `scripts/diagnose_video_package_model.py`：对视频尺寸、采样检测率和标注框面积差距做诊断。
- `scripts/audit_dataset.py`：审计 YOLO 数据集的大框、空标签负样本和 group split 泄漏风险。
- `scripts/audit_dataset_README.md`：说明数据集审计工具的运行方法和输出文件。
- `scripts/augment_yolomask_background.py`：对 YOLO 分割数据集做背景增强，只改 `parcel` mask 外像素并原样复制分割标签。
- `scripts/train_yolomask_yolo26seg.py`：按本机 GPU 显存选择 YOLOMask 分割训练参数，并用本地 GitHub 源码启动训练。
- `scripts/prepare_cvds_crossbelt_package_yolo26.py`：在原包裹数据集基础上生成交叉带小目标增强数据集。
- `scripts/extract_crossbelt_annotation_frames.py`：从真实交叉带视频抽帧，供人工标注。
- `apps/cvds_qt_app.py`：Qt GUI 主程序，负责训练可视化、图片/视频检测展示和 PLC 事件输出。
- `apps/cvds_cpp_detector/CMakeLists.txt`：C++/Qt 在线包裹流量监测软件的构建配置。
- `apps/cvds_cpp_detector/src/MainWindow.cpp`：C++ 看板界面，负责 Stitch A 布局、路径脱敏、视频源、多 ROI 编辑、KPI、区域状态表、闪烁告警和 worker 状态解析。
- `apps/cvds_cpp_detector/src/RegionConfig.cpp`：严格读取、校验和原子保存 `regions.json`，维护区域配置和运行状态结构。
- `apps/cvds_cpp_detector/src/RuntimePaths.cpp`：统一解析安装目录、worker、weights、configs 和用户 AppData 输出目录。
- `apps/cvds_cpp_detector/scripts/worker_entry.py`：打包成 `cvds_detector_worker.exe` 的统一入口，提供多格式检测、模型检查、视频源测试和环境自检。
- `apps/cvds_cpp_detector/scripts/pt_video_flow_monitor.py`：通过 Ultralytics 统一运行 PT、ONNX、OpenVINO 推理，并完成 ByteTrack、多 ROI 计数、堵包告警和输出。
- `apps/cvds_cpp_detector/scripts/inspect_model_metadata.py`：严格读取 PT、ONNX、OpenVINO 模型元数据，供界面生成类别列表。
- `apps/cvds_cpp_detector/configs/bytetrack.yaml`：随安装包发布的 ByteTrack 默认配置。
- `apps/cvds_cpp_detector/configs/regions.example.json`：主线、左分流、右分流的多 ROI 示例配置。
- `apps/cvds_cpp_detector/packaging/build_release.ps1`：一键生成发布目录和安装包。
- `apps/cvds_cpp_detector/packaging/make_installer.iss`：Inno Setup 安装器脚本。
- `apps/cvds_cpp_detector/packaging/requirements-worker.txt`：Python worker 打包依赖。
- `archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool.py`：历史 Qt AI 辅助标注工具。
- `archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool_v2.py`：历史标注工具 2.0。
- `apps/cvds_annotation_tool_legacy/`：标注工具历史单文件版和早期 SAM 集成说明，保留用于追溯，不作为当前发布入口。
- `apps/cvds_annotation_tool_v2_3.py`：标注工具 v2.3 兼容入口，只负责调用 `cvds_annotation_tool.main`。
- `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/legacy_v2_3.py`：v2.3 桌面主界面，保留 v2.2 标注、缺陷、Undo/Redo、SAM 和 AI 批量能力，并接入 v2.3 路径、诊断、安全保存、质检和导出。
- `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/runtime_paths.py`：统一管理安装目录和用户 AppData 目录，默认输出、日志、备份、缓存都写入用户目录。
- `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/services/backup_service.py`：原子写入、自动备份和回收站移动。
- `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/services/dataset_quality.py`：扫描输出数据集并生成质量报告和类别分布 CSV。
- `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/services/dataset_export.py`：按 train/val 导出标准 YOLO 数据集，可生成 zip。
- `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/services/diagnostics.py`：输出 PySide6、Ultralytics、Torch、CUDA、OpenCV、Numpy、YAML 和权重状态。
- `apps/cvds_annotation_tool_v2_3/packaging/build_release.ps1`：标注工具 v2.3 发布脚本；默认生成基础版，加 `-IncludeAI` 时生成 `CVDS_Annotation_Tool_v2.3_AI`。
- `apps/cvds_annotation_tool_v2_3/packaging/cvds_annotation_tool.spec`：标注工具 v2.3 PyInstaller 配置，通过环境变量切换基础版和 AI 版包名、依赖收集策略。
- `apps/cvds_annotation_tool_v2_3/packaging/requirements-ai.txt`：AI 版依赖声明，包含 Torch、TorchVision 和 Ultralytics。
- `apps/DatasetAssistant/CMakeLists.txt`：数据集制作助手 V1.0 构建配置，编译核心库、Qt GUI、CTest 测试和发布安装目标。
- `apps/DatasetAssistant/src/app/MainWindow.cpp`：数据集制作助手主窗口，组织工程、图片批处理、标注转换、数据集划分、模型推理、任务队列和诊断页面。
- `apps/DatasetAssistant/src/app/main.cpp`：数据集制作助手 CLI 入口，支持版本、诊断、图片批处理和数据集划分命令。
- `apps/DatasetAssistant/src/core/ProjectManager.cpp`：保存和加载工程 JSON，记录数据集路径、格式、变换、划分和推理参数。
- `apps/DatasetAssistant/tests/test_no_jam_feature.cpp`：防止堵包视频制作功能重新回到 DatasetAssistant V1.0。
- `apps/dws_batch_model_validator/src/dws_validator`：DWS 顶视图包裹检测/计数核心逻辑，包含配置、标签计数、YOLO segmentation 推理、判定、指标统计、可视化和批处理 runner。
- `apps/dws_batch_model_validator/src/dws_validator_gui`：DWS 批量验证图形界面，负责路径参数、开始/取消、环境自检、进度、日志、摘要和可视化预览。
- `apps/dws_batch_model_validator/packaging/build_release.ps1`：DWS 工具 PyInstaller 发布脚本，执行测试、诊断、GUI smoke test、打包和 zip 生成。
- `apps/dws_batch_model_validator/packaging/make_installer.iss`：DWS 工具 Inno Setup 安装脚本。
- `apps/DWSVisionCountService/app/windows_app.py`：Windows 视觉计数控制台，负责服务状态、运行参数保存和完整重启。
- `apps/DWSVisionCountService/app/roi_canvas.py`：选择现场图片并绘制检测矩形、输送带多边形和忽略矩形。
- `apps/DWSVisionCountService/app/roi_editor.py`：保证窗口缩放前后仍使用准确的原图 ROI 坐标。
- `apps/DWSVisionCountService/app/windows_settings.py`：保存前严格校验端口、模型、推理参数和 ROI。
- `apps/DWSVisionCountService/scripts/build_windows_release.ps1`：生成带统一图标、签名和 TCP 烟测的 Windows 安装包。
- `archive/legacy_tests/cvds_annotation_tool/`：历史标注工具的标签读写和路径规则测试。
- `tests/test_cpp_detector_structure.py`：C++ 检测部署版的文件结构、界面功能和推理关键逻辑测试。
- `tests/test_augment_yolomask_background.py`：分割背景增强的像素保护、标签复制和负样本背景裁剪测试。
- `tests/test_train_yolomask_yolo26seg.py`：YOLOMask 训练参数选择和本地源码优先导入测试。
- `scripts/prepare_cvds_parcel_yolo26.py`：早期脚本，曾用于 PackDet/Open Images 包装物数据；当前不作为主流程。
- `weights/cvds_yolo26n_package_best.pt`：当前默认最佳包裹检测权重，已切换为 GPU 训练版。
- `weights/cvds_yolo26n_package_gpu_best.pt`：GPU 训练版权重备份。
- `weights/cvds_yolo26n_package_cpu_best.pt`：CPU 采样训练旧权重备份。
- `weights/cvds_yolo26n_package_crossbelt_fast_best.pt`：交叉带增强候选权重，未作为默认正式权重。
- `weights/pretrained/yolo26s-seg.pt`：YOLOMask 分割训练使用的 COCO 预训练权重。
- `dist/CVDS_Qt_Platform/CVDS_Qt_Platform.exe`：Windows 可直接启动的 GUI 程序。
- `dist/CVDS_Annotation_Tool_v2.3/CVDS_Annotation_Tool_v2.3.exe`：标注工具 v2.3 基础发布包，不内置 Torch，基础手工标注可用。
- `dist/CVDS_Annotation_Tool_v2.3_AI/CVDS_Annotation_Tool_v2.3_AI.exe`：标注工具 v2.3 AI 发布包，内置 CUDA Torch、TorchVision、Ultralytics 和 OpenCV。
- `dist/dws_batch_model_validator/dist/DWSBatchModelValidator/DWSBatchModelValidator.exe`：DWS 批量模型检测验证工具，双击打开 GUI，也支持 `--diagnose`、`--version` 和 `--cli`。
- `CVDS_Qt_Platform.spec`：PyInstaller 打包配置。
- `archive/legacy_packaging/CVDS_Annotation_Tool.spec`：历史标注工具 PyInstaller 配置。
- `archive/legacy_packaging/CVDS_Annotation_Tool_v2.spec`：历史标注工具 2.0 PyInstaller 配置。

## 数据目录

- `datasets/cvds_package_yolo26`：当前可训练的包裹检测数据集。
- `datasets/cvds_package_yolo26_crossbelt`：加入交叉带小目标增强样本的数据集。
- `datasets/cvds_crossbelt_annotation_seed`：从真实交叉带视频抽出的待标注图片。
- `datasets/cvds_annotation_yolo_labeled_20260508`：从标注工具输出中筛出的有效人工标注数据，已重新切分并增强训练集。
- `datasets/cvds_20260512_yolomask`：按视频片段切分后的 YOLO 分割数据集，保留 `parcel` 多边形标签。
- `datasets/cvds_20260512_yolomask_bg_aug_20260513`：在 YOLO 分割训练集上新增背景增强图，mask 内像素和 segmentation 标签不变。
- `datasets/cvds_package_yolo26/data.yaml`：YOLO26 训练入口。
- `datasets/cvds_package_yolo26/dataset_report.json`：数据来源、清洗、增强和校验统计。
- `datasets/cvds_package_yolo26/previews`：抽样可视化标注预览。
- `datasets/sources/roboflow_downloads`：Roboflow 原始下载数据。
- `datasets/deprecated_wrong_packaging_packdet_openimages`：不符合需求的包装物数据，已废弃。

## 调用关系

`scripts/prepare_cvds_package_roboflow_yolo26.py`
读取 `datasets/sources/roboflow_downloads`
生成 `datasets/cvds_package_yolo26`
输出 `data.yaml`、`dataset_report.json` 和预览图。

`scripts/train_yolo26n_package.py`
读取 `datasets/cvds_package_yolo26/data.yaml`
加载 `weights/pretrained/yolo26n.pt`
输出 `runs/package_train/yolo26n_cvds_package` 和 `weights/cvds_yolo26n_package_best.pt`。

当前正式训练输出为 `runs/package_train/yolo26n_cvds_package_gpu12_clean`。

`scripts/track_count_packages.py`
读取视频或相机流
加载 `weights/cvds_yolo26n_package_best.pt`
支持检测 ROI 裁剪推理
输出带框视频、轨迹、计数结果和事件 CSV。

`scripts/diagnose_video_package_model.py`
读取视频、模型权重和数据集标签
输出采样检测统计、预览图和面积分布对比。

`scripts/audit_dataset.py`
读取 YOLO `images/` 和 `labels/`
统计每个 bbox 面积占比
输出 `bbox_area_stats.csv`、大框样本目录、可视化图、空标签负样本抽样、group split 泄漏表和质量报告
不修改原始数据集。

`scripts/augment_yolomask_background.py`
读取 `datasets/cvds_20260512_yolomask`
先完整复制原始 `images/` 和 `labels/`
只对训练集中有 `parcel` mask 的图片新增 1 张 PNG 增强图
增强只作用于 mask 外背景，分割标签直接复制原 txt
输出 `datasets/cvds_20260512_yolomask_bg_aug_20260513`、`data.yaml` 和 `dataset_report.json`。

`scripts/train_yolomask_yolo26seg.py`
读取 `datasets/cvds_20260512_yolomask_bg_aug_20260513/data.yaml`
检测本机 GPU 显存
优先导入 `D:\Demo\Vision\ultralytics` 中的 GitHub 源码
加载 `weights/pretrained/yolo26s-seg.pt`
输出 `runs/segment_train/yolo26s_seg_yolomask_bg_aug_960`、TensorBoard 事件文件和训练权重。

`scripts/extract_crossbelt_annotation_frames.py`
读取真实交叉带视频
输出待人工标注图片和 `manifest.csv`。

`scripts/build_cvds_manual_annotation_dataset.py`
读取 `datasets/cvds_annotation_yolo`
筛出有有效包裹框的图片和标签
移动到新数据集的 `source_annotated`
重新生成 `train`、`val`、`test`
只对训练集生成光照、模糊、噪声和翻转增强。

`apps/cvds_qt_app.py`
读取 `datasets/cvds_package_yolo26/data.yaml` 和模型权重
通过 Qt 线程运行训练或检测
启动时不预加载 YOLO、Torch、OpenCV 和 requests，训练、检测或 HTTP 输出时才加载对应库
训练时刷新 `results.csv` 并绘制指标曲线
训练监控页通过 `scripts/training_monitor.py` 读取最新训练目录
显示训练进程、训练轮数、进度、关键指标、权重文件时间和完整训练参数
检测时在界面显示画框画面
检测到包裹后输出 JSONL/TCP/HTTP 事件。

`apps/cvds_cpp_detector`
通过安装目录 `runtime/cvds_detector_worker.exe inspect-model` 读取 PT、ONNX、OpenVINO 模型类别
Qt 界面只保留本地文件、海康视频流、推理参数、多 ROI 管理和实时运行看板
视频源选中后用 OpenCV 读取首帧；用户选择当前区域后逐点绘制，右键或回车完成，支持 Esc/Ctrl+Z 撤回点；检测区域继续单独保留
模型、视频源和海康相机配置通过 `QSettings` 记忆；多 ROI 配置严格保存到用户 AppData 的 `configs/regions.json`
海康相机接入使用 RTSP 地址 `rtsp://user:password@ip:554/Streaming/Channels/channel`
界面使用工业深色钢灰配色，运行/停止按钮颜色分开，类别和执行设备下拉栏显示下拉图标，数字输入框显示正/倒三角调节键，方便现场鼠标操作
检测前把配置同步到输出目录 `regions.json`，再用 `--regions` 启动 worker；旧命令行 `--roi` 仍转换成 `default` 区域
Python worker 通过 JSON 行回传全局状态和 `regions[]`；每个区域独立维护累计数、区域内数、停滞秒数和堵包次数
环境自检通过 `runtime/cvds_detector_worker.exe diagnose` 输出 Python、Torch、CUDA、NVIDIA 驱动、Ultralytics、ONNX Runtime、OpenVINO 和 OpenCV 状态
PT、ONNX 支持 CPU/NVIDIA，OpenVINO 支持自动/Intel GPU/Intel NPU；显式设备不可用时直接失败。
全局累计只读取 `total_count_region`，不把 T 型口各区域相加
任一区域堵包时全局状态为 `JAM`，Qt 看板和 worker 画面同步红色闪烁；事件包含区域 ID、名称、`IO_JAM_ON` / `IO_JAM_OFF`
输出带框视频、多区域事件 CSV、堵包信号 JSONL、多区域统计 JSON、运行配置和预览图片。

`archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool.py`
读取图片文件夹或视频文件夹
可用 YOLO 模型批量生成预标注
视频先按帧间隔抽图再写入输出目录
可读取已有 YOLO 数据集目录，从 `data.yaml` 恢复类别名，从 `images/train` 和 `labels/train` 加载同名图片标签
图片列表使用 `QListView + QAbstractListModel`，避免十几万张图片逐条创建 UI 控件
图片扫描和空标签帧删除通过后台线程执行
界面中支持手工画框、拖动、缩放、选框、删框、换标签
支持复制上一张标注、跳到空标注、删除当前空帧和批量删除空标签帧
输出 `images/train`、`labels/train` 和 `data.yaml`。

`archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool_v2.py`
读取普通图片文件夹或已有 YOLO 数据集目录
从 `data.yaml` 恢复类别，从 `images/train` 和 `labels/train` 读取同名图片标签
使用统一 `Annotation` 数据模型同时处理检测框和分割多边形
保留模型列表和后台扫描，避免大图集加载卡住界面
删除当前帧后显式选中相邻帧，避免列表信号抖动导致回到第一帧
Esc 用于撤回当前多边形点、取消未完成检测框或恢复拖拽中的框调整
启动时不直接导入 torch、OpenCV、Numpy，设备状态用 `nvidia-smi` 轻量检测并缓存，AI 标注或读图时才加载重依赖
历史版本通过 `archive/legacy_packaging/CVDS_Annotation_Tool_v2.spec` 打包为独立 Windows exe。

`apps/cvds_annotation_tool_legacy/`
保留根目录迁出的 `cvds_annotation_tool_v2.py`、`cvds_annotation_tool_v2_2.py` 和 `sam_integration.py`
用于追溯早期单文件实现和 SAM 集成方案，不作为当前正式运行入口。

`apps/cvds_annotation_tool_v2_3.py`
命令行优先处理 `--version`、`--diagnose`、`--quality-check`、`--export-dataset`、`--qapplication-test` 和 `--window-smoke-test`
普通启动时进入 `apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/legacy_v2_3.py`
默认输出写入 `%LOCALAPPDATA%/CVDS/AnnotationTool/datasets/cvds_annotation_yolo`
基础标注功能不依赖 Ultralytics/Torch/SAM，AI/SAM 缺失只禁用增强能力或给中文提示
YOLO txt 和 defects JSON 覆盖前进入 `backups/yyyyMMdd`，写入使用 tmp + flush + replace
删除帧和批量删除空标签帧移动到输出目录 `.trash`
数据集质检写入 `reports/dataset_quality_*.json` 和 `reports/class_distribution.csv`
数据集导出复制到独立目录，不修改当前工作数据集。

`apps/cvds_jam_video_synthesizer/models.py`
定义视频信息、堵塞模式、堵塞片段和项目状态，统一写入 `synthetic/simulated` 标记。

`apps/cvds_jam_video_synthesizer/core.py`
负责随机生成不重叠堵塞片段、整帧冻结插入、ROI 局部冻结、标注 JSON/CSV 导出和 `project.json` 保存加载。

`apps/cvds_jam_video_synthesizer/video_io.py`
负责 OpenCV 读取视频信息、抽帧、MP4 编码，并预留 FFmpeg 编码入口。

`apps/cvds_jam_video_synthesizer/main.py`
PySide6 桌面 GUI，负责视频导入、预览播放、矩形 ROI 绘制、片段列表编辑、后台任务、进度条、日志和中文错误提示。

`apps/cvds_jam_video_synthesizer/paths.py`
统一默认项目目录和打包后 `runtime/ffmpeg.exe` 路径，不写开发机绝对路径。

`apps/cvds_jam_video_synthesizer_app.py`
PyInstaller 使用的 GUI 启动入口。

`apps/cvds_jam_video_synthesizer/packaging/build_release.ps1`
清理本工具构建输出、创建 `.venv`、安装依赖、运行测试、调用 PyInstaller，并复制文档、版本文件和可选 `ffmpeg.exe`。

`apps/cvds_jam_video_synthesizer/packaging/make_installer.iss`
Inno Setup 安装脚本，安装到 `{autopf}/CVDS/CVDS Jam Video Synthesizer`，创建桌面和开始菜单快捷方式，支持卸载。

## 关键设计决定

- 只训练单类 `parcel`，避免把损坏区域、包装材料、商品容器误当成包裹。
- 验证集和测试集不做增强，保证评估结果能反映真实样本。
- 对训练集加入低光、过曝、阴影、眩光、模糊和噪声，贴近物流现场复杂光照。
- 跟踪不重新造轮子，使用 ByteTrack 做跨帧 ID 关联。
- 计数位置必须显式配置为过线或 ROI，避免在不同格口布局下写死判断规则。
- 训练和 worker 打包优先使用带 CUDA 的 Python 环境；当前项目 `.venv` 为 `torch 2.11.0+cu128`，`conda yolo26` 为 `torch 2.11.0+cu130`。
- GUI 使用 PySide6/Qt，而不是重新做网页界面，方便在 Windows 现场机上直接启动。
- C++ 工具只保留视频检测和流量监测，不再包含训练、训练监控、PLC 页面和 ONNX 检测入口。
- 当前现场检测以 PT 权重为准，C++ 界面启动独立 worker exe 调用 Ultralytics，避免模型转换导致检测结果漂移，也避免依赖用户系统 Python。
- C++ 看板采用 Stitch A“监控画面优先”结构：左栏约占 24%，设置按导航展开，四项 KPI 常驻，日志默认隐藏；真实路径保存在控件属性中，不把脱敏显示文本用于运行配置。
- ROI 必须由用户在视频画面上显式绘制，避免把格口、输送线或背景区域写死在程序里；多边形 ROI 用于适配非矩形格口。
- C++ 检测页的类别列表直接读取 PT 模型内容，不再写死 `parcel`；如果模型不带类别名，就直接显示 class_id，避免误导。
- 默认推理设备为自动；有 CUDA 时用 GPU，没有 CUDA 时自动切到 CPU，并在日志里说明实际设备。
- 训练监控只读取 YOLO 原生输出文件和系统进程，不改动正在训练的进程，避免影响模型训练。
- 训练监控用 `psutil` 读取进程，不再周期性启动 PowerShell，避免刷新时弹出命令行和卡住界面。
- PLC 联动先输出标准 JSON 事件，现场可由 PLC 网关或上位机转换成实际 IO 信号。
- 视频检测效果差的主因不是输入尺寸，而是公开训练集和交叉带现场视频存在视角、尺度、背景和运动模糊差距。
- 交叉带候选权重未替换默认权重，因为它对视频略有改善但仍有明显误检。
- 后续正式提升必须基于真实交叉带标注图片，而不是继续依赖合成增强。
- 标注工具选中框固定使用亮青色，类别框使用非黑非白的彩色调色板，避免在黑白背景中看不清。
- 标注工具不再默认依赖当前权重适配现场，现场数据优先走人工标注；空帧删除只处理输出目录内的抽帧图片，避免误删原始素材。
- 标注工具面对十几万张图片时，禁止逐条创建列表控件；必须使用模型列表和后台扫描，保持界面可操作。
- 标注工具读取已有 YOLO 数据集时，图片位于 `images/train` 内就按原始图片 stem 查找 `labels/train` 同名 txt，避免因文件名含空格等字符导致旧标签不显示。
- 标注工具 2.0 用一个 `Annotation` 数据模型统一检测框和分割多边形，避免维护两套读写逻辑。
- 标注工具 2.0 使用接近 VSCode 的深色工具界面，优先保证现场标注时信息密度高、对比清楚、长时间使用不刺眼。
- 标注工具 2.0 启动阶段不直接导入 torch、OpenCV、Numpy，减少软件打开时的等待；AI 标注或读图时再加载对应库。
- 标注工具 v2.3 不再依赖开发机 Anaconda 路径；源码模式使用当前 `sys.executable`，发布模式使用 PyInstaller 内置运行环境。
- 标注工具 v2.3 默认写用户 AppData，不写程序安装目录；保存失败时阻止切图，避免数据丢失。
- 标注工具 v2.3 基础版和 AI 版分开发布，避免手工标注用户承担 3GB AI 运行库；AI 版单独命名为 `CVDS_Annotation_Tool_v2.3_AI`。
- 标注工具 v2.3 AI 版先从 CUDA 12.8 源安装 Torch/TorchVision，再安装 Ultralytics，避免误装 CPU 版 Torch。
- DatasetAssistant V1.0 去除内置堵包视频制作功能，专注数据集生产流程；视频堵包合成只作为独立历史工具保留，不混入数据集助手主流程。
- DatasetAssistant 发布脚本必须签名 build exe、dist exe 和安装包，再运行诊断烟测；本机 Application Control / Device Guard 拦截不能静默忽略。
- DWS 批量验证工具不改变原有 SINGLE/MULTI/SUSPECT_MULTI/UNKNOWN 判定规则；GUI 只负责参数、进度和结果展示。
- DWS 批量验证工具默认输出写入 `%LOCALAPPDATA%/CVDS/DWSBatchModelValidator/outputs/runs`，避免安装目录权限问题。
- DWS 发布 exe 使用控制台模式，保证 `--diagnose`、`--version` 和 `--cli` 在命令行可见；无参数启动仍进入 GUI。
- 人工标注数据整理时，空标签帧不进入训练集；验证集和测试集不做增强，避免评估结果虚高。
- 分割背景增强只作用于训练集，验证集和测试集保持原样，避免评估被增强数据污染。
- 分割背景增强图使用 PNG 保存，因为 JPG 重压缩会改变 mask 内像素，不满足“包裹像素不破坏”的要求。
- 负样本背景替换只从尺寸足够的负样本中裁剪；没有合格负样本时直接报错，不做缩放补救。
- YOLOMask 分割训练使用 RTX 4050 6GB 对应的 `weights/pretrained/yolo26s-seg.pt + imgsz=960 + batch=2`，在不爆显存的前提下优先保证小包裹分割性能。
- YOLOMask 训练过程通过 TensorBoard 暴露到 `http://127.0.0.1:6006/`，直接读取 `runs/segment_train` 下的事件文件。
- 数据集审计不改写原始 `images/` 和 `labels/`，所有大框样本、负样本抽样和报告只写入独立 `audit/` 目录。
- 对相邻帧泄漏只做风险表和 group split 建议表，不直接重排数据，避免误改训练集。
- 堵塞视频合成工具作为独立 Python GUI 工具维护，核心合成逻辑不依赖 Qt，方便测试和后续接入命令行。
- 整帧冻结按真实堵包模拟处理：随机选择 1 帧，复制该帧形成静止画面，再把原视频后续帧接回，因此输出视频会比原视频更长。
- 合成输出必须在视频项目、JSON、CSV 和界面中标记为 `synthetic/simulated`，不伪装成真实监控视频。
- 随机堵塞片段必须避开视频前后 2 秒，并且目标片段不重叠；空间不足时直接报错，不自动放宽条件。
