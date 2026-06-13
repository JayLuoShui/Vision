# CVDS 视觉算法数据准备

## 项目简介

本项目用于交叉带分拣格口异常视觉检测。当前已完成包裹检测数据集、YOLO26n 训练、视频跟踪计数、Windows 可运行的 Qt GUI 程序、C++/Qt PT 视频流量监测工具，以及 DWS 批量模型检测验证工具。

## 技术架构

- 数据来源：Roboflow Universe 公开包裹数据集。
- 数据格式：YOLO26 检测格式。
- 训练类别：单类 `parcel`。
- 数据增强：低光、过曝、阴影、眩光、轻微模糊、噪声、水平翻转。
- 分割背景增强：对 `parcel` mask 外背景做模糊、灰度、亮度对比度、噪声或负样本背景替换，mask 内像素不改，分割标签不改。
- 检测模型：以 `yolo26n.pt` 为骨干框架微调。
- 跟踪计数：YOLO26 检测 + ByteTrack 跟踪 + 过线/ROI 几何计数。
- GUI 程序：PySide6/Qt，可视化训练过程、观察训练进度、展示图片/视频检测结果。
- C++ 视频流量监测：Qt6 Widgets + OpenCV 负责界面和 ROI 绘制，Ultralytics PT 权重负责视频检测和 ByteTrack 跟踪计数。
- PLC 预留接口：检测到包裹后输出 JSON 事件，支持本地 JSONL、TCP JSON、HTTP POST。
- 视频诊断：检查视频尺寸、采样检测率、目标框面积分布，用于判断是输入尺寸问题还是训练集泛化问题。
- 数据集审计：检查 YOLO 数据集中的错误大框、空帧负样本缺失和 train/val/test 泄漏风险。
- 数据集制作助手 V1.0：C++/Qt 单机工具，聚焦图片批处理、标注转换、数据集划分、ONNX 推理和诊断；已移除内置堵包视频制作功能。
- 标注工具：PySide6/Qt，支持图片文件夹 AI 预标注、视频文件夹批量抽帧、YOLO 标注保存和可视化修正。
- DWS 批量验证：Python + PySide6 + Ultralytics，支持选择模型、图片目录、标签目录、输出目录和推理参数，生成 results.csv、summary.json、vis 和错误样本目录。
- DWS 视觉计数服务：Windows 桌面软件接收 JPEG bytes，通过 INT8 OpenVINO 完成检测，并在同一 TCP 连接返回 JSON 结果。

## 本地运行

```powershell
chcp 65001
.\.venv\Scripts\python.exe .\scripts\prepare_cvds_package_roboflow_yolo26.py
```

生成结果：

```text
datasets/cvds_package_yolo26/data.yaml
datasets/cvds_package_yolo26/images/train
datasets/cvds_package_yolo26/images/val
datasets/cvds_package_yolo26/images/test
datasets/cvds_package_yolo26/labels/train
datasets/cvds_package_yolo26/labels/val
datasets/cvds_package_yolo26/labels/test
```

启动 DWS 视觉计数服务：

```text
安装包：dist_installer/DWSVisionCountService_Setup_1.1.0.exe
便携版：dist/DWSVisionCountService_1.1.0_20260608_093102/DWSVisionCountService.exe
服务端口：TCP 9100
```

重新打包：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DWSVisionCountService\scripts\build_windows_release.ps1 -Version 1.1.0
```

## 测试方法

训练首版模型：

```powershell
conda run -n yolo26 python .\scripts\train_yolo26n_package.py --name yolo26n_cvds_package_gpu12_clean --epochs 12 --imgsz 640 --batch 8 --device 0 --workers 4
```

跟踪计数示例：

```powershell
conda run -n yolo26 python .\scripts\track_count_packages.py --source D:\path\to\video.mp4 --line 320,0,320,720 --direction both --device 0 --imgsz 960 --detect-roi 0,260,1920,1080
```

启动 Qt GUI：

```powershell
.\dist\CVDS_Qt_Platform\CVDS_Qt_Platform.exe
```

启动 AI 辅助标注工具：

```powershell
.\dist\CVDS_Annotation_Tool_v2.3_AI\CVDS_Annotation_Tool_v2.3_AI.exe
```

源码方式启动 GUI：

```powershell
conda run -n yolo26 python .\apps\cvds_qt_app.py
```

PT 视频流量监测脚本：

```powershell
.\dist\CVDS_Package_Flow_Detector\runtime\cvds_detector_worker.exe detect --weights .\weights\cvds_yolo26n_package_best.pt --source .\sample.mp4 --output-dir "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs" --preview-path "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs\preview.jpg" --roi 0,0,639,0,639,359,0,359 --imgsz 960 --device auto --tracker .\dist\CVDS_Package_Flow_Detector\configs\bytetrack.yaml --jam-signal-path "$env:LOCALAPPDATA\CVDS\CVDS包裹流量检测工具\runs\jam_signals.jsonl"
```

C++ 检测部署版一键构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

构建机需要 CMake、Ninja、MSVC、Qt、OpenCV 和 Inno Setup。终端用户安装后不需要 Python、Qt、OpenCV 或 conda。

标注工具 v2.3 AI 版打包：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_annotation_tool_v2_3\packaging\build_release.ps1 -IncludeAI
```

输出：

```text
dist/CVDS_Annotation_Tool_v2.3_AI/CVDS_Annotation_Tool_v2.3_AI.exe
dist/CVDS_Annotation_Tool_v2.3_AI.zip
```

DWS 批量模型检测验证工具：

```powershell
cd .\apps\dws_batch_model_validator
..\..\dist\dws_batch_model_validator\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe
..\..\dist\dws_batch_model_validator\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --diagnose
..\..\dist\dws_batch_model_validator\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --cli --model models\yolo26-s-seg.pt --images data\images --labels data\labels --device cpu
```

CVDS 包裹堵塞视频合成工具：

```powershell
.\.venv\Scripts\python.exe -m apps.cvds_jam_video_synthesizer
```

打包 Windows onedir：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_jam_video_synthesizer\packaging\build_release.ps1
```

生成安装包：

```powershell
iscc .\apps\cvds_jam_video_synthesizer\packaging\make_installer.iss
```

代码检查：

```powershell
conda run -n yolo26 python -m ruff check .\apps\cvds_qt_app.py .\scripts\training_monitor.py .\tests\test_training_monitor.py
conda run -n yolo26 python .\tests\test_cpp_detector_structure.py
.\.venv\Scripts\python.exe -m pytest .\tests\test_cvds_jam_video_synthesizer.py
.\.venv\Scripts\ruff.exe check .\apps\cvds_jam_video_synthesizer .\tests\test_cvds_jam_video_synthesizer.py
```

源码方式启动标注工具：

```powershell
conda run -n yolo26 python .\archive\legacy_apps\cvds_annotation_tool\cvds_annotation_tool.py
```

诊断视频泛化问题：

```powershell
conda run -n yolo26 python .\scripts\diagnose_video_package_model.py --source ".\artifacts\samples\Loop Cross-Belt Sorter in real operation [VSHu55q3tE8].mkv" --weights .\weights\cvds_yolo26n_package_best.pt --imgsz 640,960,1280 --device 0
```

审计 YOLO 数据集：

```powershell
conda run -n yolo26 python .\scripts\audit_dataset.py --dataset .\datasets\cvds_annotation_yolo_labeled_20260508 --output .\audit\cvds_annotation_yolo_labeled_20260508 --large-threshold 0.2 --huge-threshold 0.4 --sample-empty 5000
```

增强 YOLO 分割数据集背景：

```powershell
.\.venv\Scripts\python.exe .\scripts\augment_yolomask_background.py --source .\datasets\cvds_20260512_yolomask --output .\datasets\cvds_20260512_yolomask_bg_aug_20260513 --seed 20260513 --splits train
```

训练 YOLOMask 分割模型：

```powershell
.\.venv\Scripts\python.exe .\scripts\train_yolomask_yolo26seg.py --data .\datasets\cvds_20260512_yolomask_bg_aug_20260513\data.yaml --project .\runs\segment_train --name yolo26s_seg_yolomask_bg_aug_960 --source-root .\ultralytics --exist-ok
```

浏览器查看训练过程：

```powershell
.\.venv\Scripts\tensorboard.exe --logdir .\runs\segment_train --host 127.0.0.1 --port 6006 --reload_interval 10
```

打开 `http://127.0.0.1:6006/`。

抽取真实交叉带标注图片：

```powershell
conda run -n yolo26 python .\scripts\extract_crossbelt_annotation_frames.py --source ".\artifacts\samples\Loop Cross-Belt Sorter in real operation [VSHu55q3tE8].mkv" --start-frame 240 --end-frame 1040 --count 120
```

当前 GPU 版训练结果：

```text
环境：conda yolo26
GPU：NVIDIA GeForce RTX 4050 Laptop GPU，约 6GB 显存
训练参数：YOLO26n，12 轮，imgsz=640，batch=8，全量训练集
验证集：mAP50=0.978，mAP50-95=0.753
测试集：mAP50=0.904，mAP50-95=0.703，Precision=0.945，Recall=0.839
最佳权重：weights/cvds_yolo26n_package_best.pt
```

当前 GUI 程序：

```text
exe 路径：dist/CVDS_Qt_Platform/CVDS_Qt_Platform.exe
默认权重：weights/cvds_yolo26n_package_best.pt
默认事件文件：runs/plc_events/package_events.jsonl
窗口功能：模型训练、训练监控、检测展示、PLC接口
默认训练/检测尺寸：960
检测页支持：检测ROI，只在指定区域内推理并把结果映射回原图
训练监控：自动读取最新训练目录，显示运行进程、训练轮数、进度条、最新指标、最好指标、权重更新时间和完整训练参数
性能优化：监控页使用 Python 进程列表读取训练状态，不再反复弹出 PowerShell；主界面启动时延迟加载 YOLO/Torch/OpenCV
```

当前 C++ PT 视频流量监测工具：

```text
源码：apps/cvds_cpp_detector
安装包路径：dist_installer/CVDS_Package_Flow_Detector_Setup_<version>.exe
默认权重：安装目录 weights 下的首个 .pt 文件
窗口功能：视觉模型选择、路径记忆、本地视频/海康相机视频流、多 ROI 新增/命名/删除/绘制/保存/加载、主统计区域、可选检测区域、实时 KPI、区域状态表、分区堵包和红色闪烁报警
界面风格：工业深色钢灰配色，运行/停止按钮颜色区分明显，类别和执行设备下拉栏有下拉图标，数字输入框增大/减小按钮为正/倒三角形
已去除：模型训练、训练监控、PLC 接口
推理链路：C++/Qt6 + OpenCV 界面；独立 Python worker exe 使用 Ultralytics PT + ByteTrack
模型类别：根据 PT 权重内的类别信息自动读取到下拉框，不再写死 parcel
默认设备：自动；有 CUDA 优先用 GPU，没有 CUDA 自动切到 CPU；环境自检会显示 NVIDIA 驱动、Torch 版本和 Torch CUDA 状态
预览 FPS：60
统计规则：各 ROI 独立计数；顶部累计数量只取 total_count_region，T 型口不重复相加
输出文件：regions.json、pt_video_flow_monitor.mp4、flow_events.csv、jam_signals.jsonl、flow_summary.json、cvds_pt_preview.jpg
堵包规则：每个 ROI 独立判断；任一区域堵包时全局状态为 JAM，输出带区域信息的 IO_JAM_ON；解除时输出 IO_JAM_OFF
当前状态：已完成多 ROI worker、Qt 区域管理、看板、分区堵包、旧 --roi 兼容和示例配置入包
```

当前标注工具：

```text
历史 exe：artifacts/releases/archive/dist/CVDS_Annotation_Tool/CVDS_Annotation_Tool.exe
历史源码：archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool.py
2.0 历史 exe：artifacts/releases/archive/dist/CVDS_Annotation_Tool_v2.0/CVDS_Annotation_Tool_v2.exe
2.0 历史源码：archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool_v2.py
历史单文件版：apps/cvds_annotation_tool_legacy/
2.3 入口：apps/cvds_annotation_tool_v2_3.py
2.3 模块：apps/cvds_annotation_tool_v2_3/cvds_annotation_tool/
2.3 打包脚本：apps/cvds_annotation_tool_v2_3/packaging/build_release.ps1
2.3 基础版：dist/CVDS_Annotation_Tool_v2.3/CVDS_Annotation_Tool_v2.3.exe
2.3 AI版：dist/CVDS_Annotation_Tool_v2.3_AI/CVDS_Annotation_Tool_v2.3_AI.exe
2.3 AI版依赖：Torch 2.11.0+cu128、TorchVision 0.26.0+cu128、Ultralytics 8.4.53
默认输出：%LOCALAPPDATA%/CVDS/AnnotationTool/datasets/cvds_annotation_yolo
默认标签：parcel，可在界面中逐行自定义
标注格式：YOLO txt + data.yaml
目标框颜色：类别框使用彩色调色板，选中框固定亮青色 #00E5FF，避免黑白背景看不清
2.0 界面：使用接近 VSCode 的深色工具界面，控件、列表、表格和状态栏统一风格
2.0 标注模式：支持检测框和分割多边形两种模式，自动识别 YOLO det/seg 标签格式
2.0 视图操作：支持鼠标滚轮缩放、中键或 Ctrl+左键拖拽、双击重置视图
2.0 快捷操作：支持 A/D 翻页、PgUp/PgDn 跳 10 张、Home/End、Space 保存、Esc 撤回当前点或取消当前绘制、Delete 删除框、Ctrl+E 跳空标注、Ctrl+G 聚焦跳转框
手工辅助：支持框拖动、四角缩放、保存并下一张、清空当前框、复制上一张框、跳到空标注、删除当前空帧、批量删除空标签帧
读取已有YOLO：选择已有 YOLO 数据集目录后，点击“读取YOLO目录”，会读取 data.yaml 类别、images/train 图片和 labels/train 同名标签并显示已打框
空帧删除：只删除输出目录中的抽帧图片和对应标签，不删除原始视频或原始图片文件夹
大图集优化：图片列表使用轻量模型列表，图片扫描和空标签帧删除在后台线程执行，适合十几万张图片
启动优化：2.0 启动时不直接导入 torch、OpenCV、Numpy，设备状态只检测一次并缓存；AI 标注或读图时才加载重依赖
2.3 安全增强：移除本机 Anaconda 硬编码，保存使用原子写入和自动备份，删除进入 .trash 回收站
2.3 生产功能：新增环境自检、数据集质检、数据集导出、错误报告复制、AI 批量模式和任务取消
2.3 发布策略：基础版保留轻量手工标注能力；AI版单独输出为 CVDS_Annotation_Tool_v2.3_AI，内置 CUDA Torch 和 Ultralytics
```

当前人工标注训练集：

```text
数据集路径：datasets/cvds_annotation_yolo_labeled_20260508
训练入口：datasets/cvds_annotation_yolo_labeled_20260508/data.yaml
原始有效标注：891 张图片，1582 个包裹框
原始切分：train 714，val 93，test 84
增强后切分：train 3570，val 93，test 84
增强方式：低光、阴影眩光、运动模糊噪声、增强亮度后水平翻转
预览图：datasets/cvds_annotation_yolo_labeled_20260508/previews
数据报告：datasets/cvds_annotation_yolo_labeled_20260508/dataset_report.json
审计报告：audit/cvds_annotation_yolo_labeled_20260508/dataset_quality_report.md
审计结论：3747 张图片全部为正样本，空标签图片 0 张；6678 个 bbox 中 1244 个超过 20%，1221 个超过 40%
```

当前分割背景增强数据集：

```text
源数据集：datasets/cvds_20260512_yolomask
输出目录：datasets/cvds_20260512_yolomask_bg_aug_20260513
训练入口：datasets/cvds_20260512_yolomask_bg_aug_20260513/data.yaml
增强范围：只增强 train，有 mask 的 232 张图片各新增 1 张 PNG 增强图；val/test 不增强
增强方式：mask 外随机使用高斯模糊、灰度化、亮度/对比度扰动、随机噪声、负样本背景裁剪替换
保护规则：mask 内像素保持不变，增强标签直接复制原 YOLO 分割标签
数据规模：原始 730 张全部复制，新增增强图 232 张，输出共 962 张
策略分布：background_crop 48、brightness_contrast 52、gaussian_blur 46、grayscale 41、noise 45
验证结果：232 张增强图标签一致，PNG 读回后 mask 内像素一致
```

当前 YOLOMask 分割训练：

```text
源码：D:\Demo\Vision\ultralytics，GitHub 远端为 https://github.com/ultralytics/ultralytics.git，已快进到 origin/main。
预训练权重：D:\Demo\Vision\yolo26s-seg.pt。
训练数据：datasets/cvds_20260512_yolomask_bg_aug_20260513/data.yaml。
训练输出：runs/segment_train/yolo26s_seg_yolomask_bg_aug_960。
浏览器监控：http://127.0.0.1:6006/。
硬件选择：RTX 4050 Laptop GPU，约 6GB 显存；使用 YOLO26s-seg、imgsz=960、batch=2、workers=2、AdamW、cos_lr、amp。
当前状态：训练已启动，计划 120 轮，patience=25；第 1 轮 mask mAP50=0.75757、mask mAP50-95=0.55540。
```

本轮视频诊断结论：

```text
测试视频尺寸：MP4 为 640x360，MKV 为 1920x1080。
640/960/1280 采样推理都不理想，因此不是单纯输入尺寸错误。
原训练集标注框面积中位数约 35%，视频中包裹通常远小于这个比例。
主要问题是训练集缺少真实交叉带视角、运动模糊、远距离小包裹和现场背景。
```

本轮候选模型：

```text
候选权重：weights/cvds_yolo26n_package_crossbelt_fast_best.pt
训练集：datasets/cvds_package_yolo26_crossbelt
训练参数：YOLO26n，960 输入，batch 8，12 轮，抽样 35%
验证集：mAP50=0.697，mAP50-95=0.513
视频采样：旧模型 5/30 帧有检测，新模型 7/30 帧有检测，但新模型仍有大框误检。
结论：候选模型只作对比保留，未替换默认正式权重。
```

PLC 事件格式：

```json
{
  "event_type": "package_detected",
  "timestamp_ms": 1778118450308,
  "source": "video_or_image_path",
  "frame_index": 1,
  "package_count": 1,
  "boxes": [
    {
      "class_id": 0,
      "class_name": "parcel",
      "confidence": 0.67,
      "xyxy": [211, 40, 592, 618]
    }
  ]
}
```

## 搜索记录

- Roboflow Public Packages Dataset：公开页显示该数据集是门口快递包裹，类别为 `packages`，Public Domain。地址：https://public.roboflow.com/object-detection/packages-dataset
- Roboflow Universe 搜索 `packages dataset object detection class:packages`，筛出 `project-33xgh/packages-rg6yr` 和 `project-33xgh/package-73wdr`。
- Roboflow Universe 搜索 `parcel object detection package`，筛出 `deteksipaketrusak/package-kglu1`，只使用其中 `package` 类，跳过 `Damaged` 类。
- PackDet 和 Open Images 的 Box/Carton/Cardboard/Plastic bag 属于商品包装物或容器，不符合“物流包裹整体检测”，已移到废弃目录，不作为训练数据。
- skills.sh 本轮未找到比 Roboflow Universe 更直接的公开包裹检测数据源。
- GitHub 搜索 Codex 视觉算法相关 skills，采用 `vadimcomanescu/codex-skills` 中的 `senior-computer-vision`、`senior-data-scientist`、`code-reviewer`；官方 skills 列表脚本本机访问返回 HTTP 403。地址：https://github.com/vadimcomanescu/codex-skills
- GitHub `codex-skills` 主题按星标排序，最高星仓库为 `sickn33/antigravity-awesome-skills`，约 36.6k stars；已安装其 README 推荐的通用 starter skills：`brainstorming`、`test-driven-development`、`debugging-strategies`、`lint-and-validate`、`security-auditor`、`frontend-design`、`api-design-principles`、`create-pr`。地址：https://github.com/sickn33/antigravity-awesome-skills
- 2026-05-22 搜索 Windows 发布方案：skills.sh 未找到比当前本地 `test-driven-development`、`lint-and-validate` 更直接的打包专用 skill；GitHub/PyInstaller 官方说明 PyInstaller 可把 Python 解释器和依赖打进独立程序，适合当前 worker exe 方案。地址：https://github.com/pyinstaller/pyinstaller
- 2026-05-22 搜索 Qt 发布方案：Qt/PyInstaller 文档提示 Windows 发布时需要收集 Qt 插件和运行库，当前 C++ GUI 使用 `windeployqt` 完成 Qt 运行库收集。地址：https://doc.qt.io/qtforpython-6.5/deployment/deployment-pyinstaller.html
- 2026-06-01 搜索开源数据集制作/标注软件：CVAT 强在协作、质量控制、20+ 格式和 API，但部署重；Label Studio 强在多类型数据、项目管理、模型预标注，但 Web/服务端成本高；LabelImg 轻量快捷但已归档；LabelMe 单机 Qt、多形状标注和 COCO/VOC 导出好，但偏通用；X-AnyLabeling AI 标注和多模型后端强，但功能重且 GPL。DatasetAssistant V1.0 只吸收格式兼容、质量检查、轻量单机、项目化和 AI 可选方向，不引入重服务端和复杂账号系统。

## 已完成功能

- 下载 Roboflow 包裹相关公开数据集。
- 读取 YOLO26 标注和多边形标注。
- 将多边形标注转换成包裹外接框。
- 统一类别为 `parcel`。
- 对训练集加入复杂光照增强。
- 生成预览图和数据报告。
- 完成 YOLO26n 首版训练。
- 完成移动包裹跟踪与计数脚本。
- 完成 Qt GUI 程序。
- 完成训练监控界面，可观察训练参数、当前进度、指标曲线和权重文件。
- 完成训练监控卡顿和命令行弹窗优化，并安装 ruff 检查工具。
- 完成 Windows onedir exe 打包。
- 完成 PLC JSONL/TCP/HTTP 事件输出预留接口。
- 完成视频尺寸与泛化诊断脚本。
- 完成 YOLO 数据集审计工具，可输出大框统计、可视化、空标签负样本抽样和 group split 泄漏风险表。
- 完成 YOLO 分割背景增强工具，增强 mask 外背景并保持 `parcel` 像素和 segmentation 标签不变。
- 完成 YOLOMask 分割训练入口，使用本地 GitHub 源码、YOLO26s-seg 预训练权重和 TensorBoard 浏览器监控。
- 完成交叉带小目标增强数据集。
- 完成真实交叉带视频抽帧标注种子集。
- 完成一版交叉带候选模型训练，但未替换正式默认权重。
- 完成 AI 辅助 YOLO 标注工具，并打包 Windows exe。
- 完成标注工具手工辅助改造，支持真实交叉带现场图片手工标注和空帧清理。
- 完成标注工具大图集性能优化，减少十几万张图片加载时的界面卡顿。
- 完成标注工具读取已有 YOLO 数据集并显示已打标签。
- 完成标注工具 2.0，新增检测框/分割多边形双模式、VSCode 风格界面和独立 Windows exe。
- 完成标注工具 v2.3 基础版和 AI 版双发布包；基础版保留手工标注，AI 版内置 CUDA Torch、TorchVision 和 Ultralytics。
- 完成 DWS 批量模型检测验证工具 Windows GUI 和 CLI 发布包，支持 CPU 推理、环境自检、实时进度、日志、可视化预览、取消任务和 PyInstaller 打包。
- 完成人工标注数据整理，将有效标注样本移出并重新切分为训练、验证、测试集，同时完成训练集增强。
- 完成 C++/Qt PT 视频流量监测工具，去除训练、训练监控和 ONNX 检测入口。
- 完成 C++ 发布形态改造：GUI 调用 `runtime/cvds_detector_worker.exe`，不再默认依赖开发机 Python。
- 完成 C++ 检测页 PT 推理链路优化：自动/CPU/GPU 三种模式、预览 FPS 默认 60。
- 完成 C++ 检测页多边形 ROI 绘制和流量监测：视频首帧逐点画 ROI，右键或回车完成，支持撤回点，可选检测区域，支持路径记忆和海康相机 RTSP 视频流，输出带框视频、事件 CSV、堵包信号 JSONL 和统计 JSON。
- 完成 C++ 多 ROI 看板：区域新增/命名/删除/保存/加载、主统计区域、分区计数、分区堵包、KPI、区域状态表和红色闪烁告警；旧 `--roi` 命令继续兼容。
- 完成 Windows 安装包脚本：`apps/cvds_cpp_detector/packaging/`、worker requirements 和发布文档。
- 完成 CVDS 包裹堵塞视频合成工具首版：支持视频导入、抽帧、矩形 ROI、随机/手动堵塞片段、整帧冻结插入、ROI 冻结、合成帧、MP4 导出、`jam_segments.json/csv`、`project.json` 和 Windows 打包脚本；所有合成结果明确标记为 `synthetic/simulated`。
- 完成 DatasetAssistant V1.0 功能收敛：移除内置堵包视频制作页面、CLI、工程字段、核心代码和测试，保留图片批处理、标注转换、数据集划分、模型推理和诊断。

## 待办事项

- 用现场格口视频采样补充真实物流场景数据。
- 增加人员遮挡和反光难例。
- 按相机位和格口类型重新划分训练、验证、测试集。
- 到现场 PLC 网关环境联调 TCP 或 HTTP 输出。
- 使用 `datasets/cvds_annotation_yolo_labeled_20260508/data.yaml` 训练新的现场适配模型。
