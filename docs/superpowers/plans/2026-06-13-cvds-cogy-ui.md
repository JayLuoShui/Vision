# CVDS COGY UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 CVDS C++ Detector 2.0 改造成 Stitch A 版深色工业监控台，并把 COGY 氪技 Logo 统一用于界面和 Windows 发布物。

**Architecture:** 保留现有 `MainWindow` 功能结构，通过 Qt Widgets、QSS 和 Qt Resource System 调整视觉层级。品牌图片转换为顶部 Logo 和多尺寸 Windows 图标，资源嵌入 EXE；发布脚本继续沿用现有 Qt、worker、Inno Setup 和签名流程。

**Tech Stack:** C++17、Qt 6 Widgets/QRC、CMake、Python/Pillow 资源转换、Pytest、Inno Setup、Windows Authenticode。

---

### Task 1: 锁定 UI 和品牌资源契约

**Files:**
- Modify: `tests/test_cpp_detector_structure.py`

- [ ] **Step 1: 写失败测试**

新增断言：`assets/cogy_brand.png`、`assets/cogy_app.ico`、`src/resources.qrc`、`src/app_icon.rc` 存在；CMake 引用资源；主窗口包含 `brandBar`、`brandLogo`、`systemStatus`；QSS 包含 Stitch A 版色值。

- [ ] **Step 2: 确认测试失败**

Run: `D:\Demo\Vision\.venv\Scripts\python.exe -m pytest tests/test_cpp_detector_structure.py -q`

Expected: FAIL，原因是品牌资源和新 UI 尚不存在。

### Task 2: 生成并嵌入 COGY 品牌资源

**Files:**
- Create: `apps/cvds_cpp_detector/assets/cogy_brand.png`
- Create: `apps/cvds_cpp_detector/assets/cogy_mark.png`
- Create: `apps/cvds_cpp_detector/assets/cogy_app.ico`
- Create: `apps/cvds_cpp_detector/src/resources.qrc`
- Create: `apps/cvds_cpp_detector/src/app_icon.rc`
- Modify: `apps/cvds_cpp_detector/CMakeLists.txt`

- [ ] **Step 1: 由原始 JPG 生成资源**

使用仓库 `.venv` 的 Pillow：完整图裁掉纯白外边距后输出透明背景 PNG；左侧图形标志按内容裁切、留 8% 安全边距并生成 16/24/32/48/64/128/256px ICO。

- [ ] **Step 2: 建立 Qt 和 Windows 资源入口**

`resources.qrc` 将完整 Logo 和方形标志映射为 `:/branding/cogy_brand.png`、`:/branding/cogy_mark.png`；`app_icon.rc` 将 ICO 作为 `IDI_ICON1 ICON` 嵌入 Windows 可执行文件。

- [ ] **Step 3: 更新 CMake**

把 QRC 和 Windows RC 加入 `add_executable`，并在安装阶段复制品牌图供安装程序使用。

- [ ] **Step 4: 运行结构测试**

Run: `D:\Demo\Vision\.venv\Scripts\python.exe -m pytest tests/test_cpp_detector_structure.py -q`

Expected: 品牌资源相关断言通过，UI 断言仍失败。

### Task 3: 实现 Stitch A 版 Qt 界面

**Files:**
- Modify: `apps/cvds_cpp_detector/src/MainWindow.h`
- Modify: `apps/cvds_cpp_detector/src/MainWindow.cpp`
- Modify: `apps/cvds_cpp_detector/src/main.cpp`

- [ ] **Step 1: 增加顶部品牌状态栏**

在根布局上方增加 `brandBar`，完整 Logo 高度 38px，产品名显示“CVDS C++ DETECTOR / 多区域包裹流量监测”，右侧显示版本和绿色“系统就绪”状态。

- [ ] **Step 2: 调整 A 版信息层级**

主布局改为纵向根布局加水平 splitter；左栏默认 312px；KPI 区控制在 104px；视频区继续使用伸展因子 1；区域表保持 120-154px；日志默认隐藏。

- [ ] **Step 3: 替换视觉系统**

统一使用设计说明中的背景、面板、边框、文字和状态色；主操作使用 COGY 蓝，停止按钮使用红色；ROI 当前区域使用蓝色，其他区域使用琥珀色，检测 ROI 使用青色。

- [ ] **Step 4: 收敛堵包告警**

堵包时只闪烁视频边框、看板卡片边框和红色状态文字，不覆盖整个根窗口背景。

- [ ] **Step 5: 设置应用图标**

`main.cpp` 从 `:/branding/cogy_mark.png` 设置应用图标，Windows EXE 图标由 RC 提供。

- [ ] **Step 6: 运行结构测试**

Run: `D:\Demo\Vision\.venv\Scripts\python.exe -m pytest tests/test_cpp_detector_structure.py -q`

Expected: PASS。

### Task 4: 构建和界面验收

**Files:**
- Modify only if validation finds defects.

- [ ] **Step 1: 运行项目测试**

Run: `D:\Demo\Vision\.venv\Scripts\python.exe -m pytest -q`

Expected: 全部通过。

- [ ] **Step 2: 运行静态检查**

Run: `D:\Demo\Vision\.venv\Scripts\python.exe -m ruff check apps/cvds_cpp_detector tests/test_cpp_detector_structure.py`

Expected: 0 个问题。

- [ ] **Step 3: Release 编译**

使用现有 Qt/OpenCV CMake 环境配置并构建 `CVDS_Cpp_Detector.exe`。

- [ ] **Step 4: 启动验收**

隐藏启动确认无崩溃，再打开正式窗口检查 Logo、品牌栏、KPI、视频占比、区域表和日志折叠。

### Task 5: 更新正式发布物并签名

**Files:**
- Modify: `apps/cvds_cpp_detector/packaging/make_installer.iss`
- Modify: `dist/CVDS_Cpp_Detector2.0/CVDS_Cpp_Detector.exe`
- Modify: `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`

- [ ] **Step 1: 让安装程序使用品牌图标**

在 Inno Setup `[Setup]` 中设置 `SetupIconFile`，继续使用 EXE 作为卸载图标。

- [ ] **Step 2: 更新正式 GUI**

关闭旧 GUI 进程，把新编译 EXE 和品牌资源更新到现有 `dist/CVDS_Cpp_Detector2.0`，保留已验证 worker 和模型目录。

- [ ] **Step 3: 数字签名**

使用 `CN=CVDS Local Code Signing` 签名 GUI、worker 和安装包，并逐个检查 Authenticode 为 Valid。

- [ ] **Step 4: 重建安装包**

调用现有 Inno Setup 配置生成 `CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`。

### Task 6: Review 和项目记录

**Files:**
- Modify: `apps/cvds_cpp_detector/task_plan.md`
- Modify: `apps/cvds_cpp_detector/progress.md`
- Modify: `apps/cvds_cpp_detector/findings.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: Review 查 Bug**

检查布局尺寸、资源路径、告警样式、无障碍对比度、发布目录和签名状态。

- [ ] **Step 2: 第一性原理复盘**

确认所有改动都服务于“监控画面最大、信息完整、品牌统一”，删除无用样式和未使用成员。

- [ ] **Step 3: 更新记录**

只记录最终实现、验证数量、发布路径和签名结果。
