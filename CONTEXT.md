# 当前上下文

当前正在做什么：2026-06-29 已修复 CVDS Cpp Detector `v2.4.3` 顶栏控制面板按钮高度不一致。

上次停在哪个位置：“收起/展开控制面板”按钮现固定为 120×40px，与顶栏相邻状态框等高；PySide6 mock、正式 EXE 和安装包均已更新，正式发布版已启动完成视觉核对。

近期的关键决定和原因：
- 根因是按钮只固定宽度，高度仍使用 QPushButton 自身尺寸提示；使用 `setFixedHeight(40)` 与 52px 顶栏及上下 5px 边距直接对齐。
- 保持版本号 2.4.3，原路径产物已覆盖，不保留同版本旧修复包。
- 2026-06-29 本次验证结果：相关检查 39/39 通过；Ruff 0 个问题；C++ Release 编译、EXE 签名、安装包生成和签名均通过。

当前正在做什么：2026-06-29 已按确认的 PySide6 预览完成 CVDS Cpp Detector `v2.4.3` 正式发布。

上次停在哪个位置：顶栏“收起控制面板”固定为 120px；正式版同步了 52px 顶栏、94px KPI、34px 监控标题栏和 46px 底栏。便携版位于 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_2.4.3`，安装包位于 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector_2.4.3_Setup_2.4.3.exe`。

近期的关键决定和原因：
- 使用独立 2.4.3 发布目录，不覆盖已有 2.4.2。
- 主程序先签名再封装安装包，主程序和安装包签名均为 Valid；正式发布版已实际启动并完成界面核对。
- 2026-06-29 本次验证结果：相关检查 39/39 通过；Ruff 0 个问题；C++ Release 与安装包生成通过。

当前正在做什么：2026-06-29 已按修改后的 PySide6 mock UI 编译、签名并生成 CVDS Cpp Detector `v2.4.2` 发布版。

上次停在哪个位置：正式版已完成 `2.4.2` 构建与安装包生成，主程序和安装包都已用本机证书签名并验证为 Valid。

近期的关键决定和原因：
- 本次发布版只跟随已确认的 UI 改动，版本号升到 `2.4.2`。
- 2026-06-29 本次验证结果：`tests/test_cpp_detector_structure.py` 30/30 通过；`tests/test_cvds_ui_mockup.py` 8/8 通过；正式 EXE 和安装包签名均为 Valid。

当前正在做什么：2026-06-29 已调整 PySide6 mock 顶部“收起控制面板”按钮宽度。

上次停在哪个位置：按钮外框已从 130px 收回到 120px，与顶栏其他按钮更一致；mock 断言也同步更新。

近期的关键决定和原因：
- 本阶段仍只修改 mock，不同步 C++ 正式版。
- 2026-06-29 本次验证结果：PySide6 mock 检查待重新跑；自动截图待重新跑。

当前正在做什么：2026-06-29 已按用户参考图完成 CVDS PySide6 监控主界面 mock 预览。

上次停在哪个位置：mock 默认收起 320 侧栏，客户区为 1674×914；品牌栏 52、KPI 94、监控标题 34、双路画面 486、底栏 46。顶部文件名/来源/时间/版本/控制按钮/系统状态、四项 KPI 和双路检测画面均已复刻，右侧 QSS 实时编辑器保留。

近期的关键决定和原因：
- 本阶段只改 PySide6 mock，不修改或编译 C++ 正式版，先让用户确认视觉方案。
- 参考图仅用于裁取两路静态视频内容，界面外壳、文字、卡片和按钮仍由真实 Qt 控件渲染。
- 2026-06-29 本次验证结果：PySide6 mock 检查 8/8 通过；自动 `grab()` 截图通过，预览位于 `apps/cvds_ui_mockup/preview.png`。

当前正在做什么：2026-06-29 已恢复 CVDS Cpp Detector 下拉框和数字框的箭头按钮。

上次停在哪个位置：`arrow_up.xpm`、`arrow_down.xpm` 已通过 `resources.qrc` 嵌入 EXE；`cvds.qss` 的 `QComboBox`、`QSpinBox`、`QDoubleSpinBox` 均使用真实上下箭头，不再显示蓝色方块。

近期的关键决定和原因：
- 使用 9×5 透明 XPM 资源，避免新增 QtSvg 依赖或发布目录外部图片。
- 2026-06-29 本次验证结果：相关检查 37/37 通过；Ruff 0 个问题；C++ Release 编译通过；发布 EXE 签名 Valid；SHA256 为 `B47623118CBF77AFF77DAEB8CB5DB21A2A54F258CEA5649252AE0F662943B0E2`。

当前正在做什么：2026-06-29 已完整重编译、签名并生成新的 CVDS Cpp Detector EXE。

上次停在哪个位置：最新 EXE 位于 `dist/CVDS_Cpp_Detector_TensorRT_Fixed/CVDS_Cpp_Detector.exe`；构建产物先签名再复制，构建与发布文件哈希一致。

近期的关键决定和原因：
- 使用 `--clean-first` 完整重建 Qt 资源、OpenVINO、TensorRT、跟踪和主界面，避免复用旧目标文件。
- 2026-06-29 本次验证结果：相关检查 36/36 通过；Ruff 0 个问题；构建和发布 EXE 签名均为 Valid；SHA256 为 `7CDF9F6238D108986E5BAD65B21334517378AA9377A3A5C28BA61FC01859A275`。
- Smart App Control 对本机自签名证书的新哈希仍可能拦截，未修改或绕过系统安全策略。

当前正在做什么：2026-06-29 已按 `apps/cvds_ui_mockup/cvds.qss` 调整 CVDS Cpp Detector 正式界面。

上次停在哪个位置：`cvds.qss` 已通过 `resources.qrc` 嵌入 EXE，C++ 旧内嵌主体样式已删除；正式界面的标题、侧栏、面板和 KPI 对象名已与 QSS 对齐。KPI 改为“累计包裹 / 系统状态 / 当前区域状态 / 堵包次数”，内容居中，状态通过 `status` 属性显示灰蓝、红、蓝、绿。

近期的关键决定和原因：
- 主体界面只维护一份 `cvds.qss`；堵包闪烁边框保留原有局部运行时样式，避免 Windows Smart App Control 对再次重签的新哈希重复拦截。
- DPI-aware 正式版截图 `build/cvds_cpp_detector_qss_preview.png` 已确认顶栏、320 侧栏、KPI 和监控区无截断。
- 2026-06-29 本次验证结果：相关回归检查 36/36 通过；Ruff 0 个问题；C++ Release 编译通过；发布 EXE 签名 Valid，SHA256 为 `0C799A48DB9F0646E0EC633B059F49952CB778B659707AE47A302D22AD757FAB`。
- 当前限制：Smart App Control 拒绝无云信誉的新哈希；本机自签名证书虽显示 Valid，但不是 Microsoft Trusted Root Program 的受信任提供商证书，最终发布 EXE 暂不能启动。未关闭或绕过系统安全策略。

当前正在做什么：2026-06-29 已更新 CVDS PySide6 mock 的 KPI 字号和状态语义色。

上次停在哪个位置：KPI 标题为 13px、数字为 24px、状态为 16px；状态标签通过 `status` 属性着色：待机灰蓝、堵包红、检测中蓝、已完成绿。当前预览显示“已完成”绿色和区域待机灰蓝色。

近期的关键决定和原因：
- 使用 Qt 动态属性和 QSS 属性选择器，不按显示文字猜状态。
- 颜色沿用现有深色工业监控色板，不新增颜色体系。
- 2026-06-29 本次验证结果：PySide6 回归检查 7/7 通过；自动截图通过。

当前正在做什么：2026-06-29 已居中并协调 CVDS PySide6 mock 的 KPI 卡片字体。

上次停在哪个位置：四张 KPI 卡片的标题和内容已水平、垂直居中；标题保持 12px，数字调整为 22px/700，状态调整为 15px/600，上下留白对称。

近期的关键决定和原因：
- 卡片原先只在底部放弹性空间，内容会偏上；现改为上下对称弹性空间。
- 数字与双行状态使用不同字号和字重，但保持相近视觉重量。
- 2026-06-29 本次验证结果：PySide6 回归检查 6/6 通过；自动截图通过。

当前正在做什么：2026-06-29 已统一 CVDS PySide6 mock 顶部状态控件字体。

上次停在哪个位置：在线监测、版本号、收起控制面板、系统就绪四项已统一为微软雅黑 13px、500 字重、6px/10px 内边距；状态颜色保持不变，顶栏无溢出。

近期的关键决定和原因：
- 根因是三个标签单独写死为 9px，而按钮继承全局 13px；现统一到一条顶部公共样式规则。
- 2026-06-29 本次验证结果：PySide6 回归检查 5/5 通过；自动截图通过。

当前正在做什么：2026-06-29 已调整 CVDS PySide6 mock 的 KPI 卡片布局与示例内容。

上次停在哪个位置：四张 KPI 卡片已改为标题在上、内容在下；内容依次为累计包裹 1264、系统状态已完成、当前区域状态“区域1 待机/区域2 待机”、堵包次数 3；卡片条高度为 82，双行状态完整显示。

近期的关键决定和原因：
- 使用现有 `KpiTitle`、`KpiValue`、`KpiStatusMain` 样式，不新增选择器。
- 四张卡统一纵向布局，避免为第三张卡做单独补丁。
- 2026-06-29 本次验证结果：PySide6 回归检查 4/4 通过；自动截图通过。

当前正在做什么：2026-06-29 已按指定字体层级更新 CVDS PySide6 mock stylesheet。

上次停在哪个位置：`cvds.qss` 已统一为微软雅黑/Segoe UI、13px 全局字、指定标题/KPI/表格字号与颜色；`qt_preview.py` 的对象名已同步为 `AppTitle`、`SideMenu`、`SideSubtitle`、`PanelTitle`、`KpiTitle`、`KpiValue`、`KpiStatusMain`，确保规则真实命中。

近期的关键决定和原因：
- 不保留旧对象名兼容层，避免两套选择器互相覆盖。
- 只改字体样式契约，不改变 320 侧栏和控件布局。
- 2026-06-29 本次验证结果：PySide6 回归检查 3/3 通过；自动截图通过，中文、554 和 KPI 均完整显示。

当前正在做什么：2026-06-29 已新增 CVDS PySide6 实时 UI 调整 mock。

上次停在哪个位置：`apps/cvds_ui_mockup/qt_preview.py` 已复刻当前深色 QMainWindow、320 固定侧栏、四个设置页和监控区；右侧可直接编辑 `cvds.qss`，停写 250ms 后自动应用并通过 `grab()` 更新 `preview.png`，也支持外部修改 QSS 自动重载。

近期的关键决定和原因：
- 正式 C++ 界面不承担试样式工作，mock 只复刻布局和 stylesheet，不接视频与推理业务。
- 明确加载微软雅黑字体，保证无界面自动截图也能正确显示中文。
- 2026-06-29 本次验证结果：PySide6 回归检查 2/2 通过；Ruff 0 个问题；Python 编译检查通过；自动截图通过。

当前正在做什么：2026-06-26 已给 CVDS Cpp Detector 核心源码补充中文维护注释。

上次停在哪个位置：已在 `MainWindow.h`、`RegionConfig.h`、推理后端、`VideoPipeline`、`PipelineRuntimeManager`、计数、堵包、输出、WCS 发布、ByteTrack、WCS 配置和 TCP 客户端等维护入口补充“维护说明”注释；注释只解释职责边界和易错点，不改变运行逻辑。

近期的关键决定和原因：
- 不做逐行注释，只给关键类、结构体和流程入口加中文说明，避免源码变啰嗦。
- 新增结构检查要求核心源码包含中文维护注释，防止后续回退成无注释状态。
- 2026-06-26 本次验证结果：中文注释结构检查先失败后通过；Detector 结构测试 28/28 通过；Ruff 0 个问题；C++ Release 增量编译通过。

当前正在做什么：2026-06-26 已按当前源码实际情况重写 `apps/cvds_cpp_detector` 下的 Markdown 文档。

上次停在哪个位置：`README.md`、发布说明、打包说明、部署说明、WCS 说明、多 ROI 手工验收、历史计划、`task_plan.md`、`progress.md` 和 `findings.md` 已统一改为当前纯 C++ OpenVINO/TensorRT、`PipelineRuntimeManager`、单一 `CVDS_Cpp_Detector.exe` 架构；不再把 Python worker、PT/ONNX 直接推理、独立 WCS 程序当作当前运行端。

近期的关键决定和原因：
- 不删除 Markdown 文件，只重写内容，避免触发文件删除风险。
- 文档以当前 `CMakeLists.txt`、`src/` 和 `packaging/build_release.ps1` 为准，而不是历史计划。
- 2026-06-26 本次验证结果：Detector 结构测试 27/27 通过；Ruff 0 个问题。

当前正在做什么：2026-06-26 已在不覆盖原有发布包的前提下，跑通当前 GitHub 分支 `chatgpt-wcs-architecture-cleanup` 的 CVDS Cpp Detector 测试并生成独立发布包。

上次停在哪个位置：新便携版位于 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_GitHubBranch_20260626_Release`，安装包位于 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector_GitHubBranch_20260626_Release_Setup_2.4.1.exe`；原 `dist` 下已有发布目录保留未清理。主程序和安装包签名状态均为 Valid。

近期的关键决定和原因：
- 发布脚本使用独立 `DistName=CVDS_Cpp_Detector_GitHubBranch_20260626_Release`，避免覆盖 `dist` 下原有发布包。
- 结构测试已按当前 `PipelineRuntimeManager` 架构更新，不再检查已移除的旧 `CVDS_WCS_Multi_Camera_Monitor` 目录。
- 2026-06-26 本次验证结果：Detector 结构测试 27/27 通过；Ruff 0 个问题；C++ Release + TensorRT 构建通过；启动冒烟通过；便携版 SHA256 为 `AF5AD085B80907FABB840D60A9167FF67625C1BED4D87475390979F10B7D7B38`；安装包 SHA256 为 `22F4E2AAB1D66679439EA4E060C1D6E904E703FBD12409A22EA9BA9C2435D3B4`。

当前正在做什么：2026-06-26 已修复堵包解除后实时监控画面与 KPI 卡片红色边框不恢复的问题。

上次停在哪个位置：最新 `camera_1` 堵包日志显示多次 `IO_JAM_ON` 后都有 `IO_JAM_OFF`，检测解除信号正常；问题在 UI 样式恢复。`updateAlertStyle()` 现在在非报警状态下明确写回正常边框样式，不再只清空 `dashboardRoot_` 样式。

近期的关键决定和原因：
- Qt 子控件边框样式不能只依赖父级样式清空，红色边框可能视觉残留；恢复时直接写回正常 `monitorPanel / dashboardCard / QTableWidget` 边框更稳。
- 不新增状态机，不改检测逻辑，只修 UI 样式出口。
- 2026-06-26 本次验证结果：红框恢复结构检查 1/1 先失败后通过；当前 Detector 相关结构测试 25/25 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `15B6B08697B7031BFBBA07464D934721BF4FFBDDC7D9EE5C7FA99F879D268819`。

当前正在做什么：2026-06-26 已修复第二次堵包未触发红色报警的问题。

上次停在哪个位置：最新日志显示 `camera_1 / region_1` 有 `IO_JAM_ON` 和 `IO_JAM_OFF`，但报警状态被 KPI 计数口径过滤挡住。现在 `aggregateDashboardFromCameraStates()` 会先按所有相机所有区域计算当前是否存在堵包，再按左侧计数口径过滤 KPI 数值。

近期的关键决定和原因：
- 红色报警是安全提示，应跟随所有区域的当前堵包状态；累计包裹、区域内包裹和堵包次数才跟随左侧计数口径。
- 不新增报警状态字段，只把现有 `dashboardJamActive_` 的计算提前到 KPI 过滤之前，保持改动最小。
- 2026-06-26 本次验证结果：报警不受 KPI 口径过滤的结构检查 1/1 先失败后通过；当前 Detector 相关结构测试 25/25 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `251F54115A79FB11ABC8C2DA34345AB6147FAEA5D4E76F055FC44558DF3ADA4C`。

当前正在做什么：2026-06-26 已修复 CVDS Cpp Detector 堵包解除后外层红框仍残留的问题。

上次停在哪个位置：报警红框和预览红框现在统一只在 `dashboardJamActive_ && dashboardFlashVisible_` 时显示；历史堵包次数 `jam_count` 保留统计，但不会继续触发红框。截图中这种 `OCCUPIED / 堵包秒数 0.0 / 堵包次数 1` 的状态会显示为正常边框。

近期的关键决定和原因：
- 根因是 UI 红框样式只看闪烁帧状态，未把“当前是否仍在堵包”作为硬条件；解除堵包后若最后一次样式停在红色，就可能残留。
- 修复放在 `refreshRegionTable()` 和 `updateAlertStyle()` 两个共享出口，不在每个事件分支零散补丁。
- 2026-06-26 本次验证结果：堵包解除红框回归检查 1/1 先失败后通过；当前 Detector 相关结构测试 25/25 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `C4A182A850BA8EEC80469CBAA7AF089CEEF7ADF7D76AB2D9FF74A6AC6B29674E`。

当前正在做什么：2026-06-26 已去除 CVDS Cpp Detector 实时监控画面右上角“当前区域”文字。

上次停在哪个位置：`RoiPreviewLabel::paintEvent()` 不再在视频画面右上角绘制“当前区域: 区域 1”这类提示；ROI 多边形自身标签和报警红框逻辑保留。

近期的关键决定和原因：
- 用户只要求去掉画面右上角框选信息，所以只删除该处 `drawText`，不改左侧当前区域选择和 ROI 区域标签。
- 2026-06-26 本次验证结果：新增结构检查 1/1 先失败后通过；当前 Detector 相关结构测试 25/25 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `5E7391D8BACA1B86F64C7455C5C9E8C0578330982A03ECA12897A08EA06E8F9D`。

当前正在做什么：2026-06-26 已总结并记录本机 PowerShell 与 MSVC 编译命令的失败原因。

上次停在哪个位置：规则已写入 `5.lessons.md`：本机 C++ 编译固定使用 BuildTools 的 `VsDevCmd.bat` 路径；PowerShell 临时 Python 代码固定使用 here-string 管道，不再使用 Bash here-doc。

近期的关键决定和原因：
- 之前重复失败不是代码问题，而是命令写法问题：一是猜错 Visual Studio `Community` 路径，二是在 PowerShell 中使用了 Bash 的 `python - <<'PY'` 语法。
- 下次直接使用已验证命令，减少无意义重试。

当前正在做什么：2026-06-26 已修复 CVDS Cpp Detector 堵包报警恢复和未绘制 ROI 前区域详情误显示的问题。

上次停在哪个位置：堵包结束后即使闪烁定时器还有一次回调，也会先确认当前没有堵包再强制关闭红框；区域统计详情在没有闭合 ROI 且未开始检测时不再显示默认区域行，只有完成 ROI 或检测运行后才显示区域状态。

近期的关键决定和原因：
- 红色报警的根因是报警状态已清除后，闪烁回调仍可能再次刷新红框；在统一闪烁入口加保护，比在每个报警事件分支补判断更稳。
- 本地视频只选择源不等于已有 ROI，区域表不能用默认区域占位误导用户。
- 2026-06-26 日志核查：最新两路运行中 `camera_1` 输出 6674 帧、约 212.28 秒，`camera_2` 输出 5421 帧、约 180.72 秒；未发现失败、超时或异常日志。`camera_2` 中间有一段没有新增计数事件，但输出视频连续生成，现有日志不能证明检测线程中断。
- 2026-06-26 本次验证结果：新增结构测试 2/2 先失败后通过；当前 Detector 相关结构测试 25/25 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `F161A5C08D16574A5645A4D6E0DE7099E65324D48DD989A0FD6599CE246D11D2`。

当前正在做什么：2026-06-26 已修复 CVDS Cpp Detector 点击“应用本地视频”后直接播放视频的问题。

上次停在哪个位置：“应用本地视频”不再调用实时预览线程；现在会逐路只读取第一帧并合成到实时监控画面，供用户绘制 ROI。只有点击“开始检测”后，才启动视频播放和检测线程。

近期的关键决定和原因：
- 本地视频应用阶段只需要静态首帧，持续播放会影响 ROI 绘制并提前消耗视频进度。
- 复用已有 `openCapture()` 和 `composeMultiCameraPreview()`，不新增播放状态或额外线程。
- 2026-06-26 本次验证结果：新增结构测试 1/1 通过；当前 Detector 相关结构测试 24/24 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `6600F5E4D28CD0DA3BB8ED74444A2731A8B92025487364D50D29D8A09E925F01`。

当前正在做什么：2026-06-26 已修复 CVDS Cpp Detector 多路本地检测时 KPI、堵包报警、ROI 会话和预览帧率逻辑。

上次停在哪个位置：KPI 四项只跟随左侧“计数口径”聚合，不再受点击某个子画面影响；计数口径切换会立即重算 KPI 和堵包红色报警；默认区域从 `main_region/主统计区域` 改为 `region_1/区域 1`；右上角当前区域显示区域名而不是内部 ID；应用本地视频会清空旧 ROI 会话并只启动实时预览；多路检测不再把 `previewFps` 强制限制为 8，预览线程间隔从 125ms 恢复到 33ms。

近期的关键决定和原因：
- 根因是看板同时被“当前区域”和“点击子画面”两套状态过滤，导致 KPI 和报警不跟随左侧计数口径；现在只用计数口径过滤。
- 旧 ROI 属于本地视频会话状态，重新应用本地视频时清空，避免复测时残留旧 ROI。
- 2026-06-26 本次验证结果：当前 Detector 相关结构测试 24/24 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `B6D72C5054431B313453EB129AED2EB85943B61975F8F71CCEEA7E04B70C50CC`。

当前正在做什么：2026-06-26 已修复 CVDS Cpp Detector 未选择本地文件前仍显示上次本地视频的问题。

上次停在哪个位置：启动加载设置时不再恢复 `lastSourcePath` 和 `multiSourcePaths`；保存设置时会删除这两个旧键。软件打开后，本地文件框和多路视频源默认为空，只有本次点击“选择”后才追加本地视频路径到多路视频源。

近期的关键决定和原因：
- 本地视频源改为本次会话配置，避免用户还没选择文件就看到上次的旧视频，导致误判当前检测源。
- 海康 IP、密码、通道等仍按原逻辑恢复，因为这是设备连接配置，不属于本地视频选择状态。
- 2026-06-26 本次验证结果：新增结构测试 1/1 通过；当前 Detector 相关结构测试 24/24 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `BCD65AA8AF2994F2DB4E939756B32F9208E1E7AE416B9AD0A3A8C7AA581AAAB7`。

当前正在做什么：2026-06-26 已优化 CVDS Cpp Detector 本地文件选择和多路本地视频源填写逻辑。

上次停在哪个位置：点击“选择”本地视频后，单行“本地文件”框不再显示真实文件名，只显示“已加入多路视频源”；真实视频路径会追加到“多路视频源”文本框中，多次选择会形成多路本地视频列表，点击“应用本地视频”后复用已有多路预览和多路检测逻辑。

近期的关键决定和原因：
- 不新增批量导入窗口或新检测分支，只复用现有多路文本框、`configuredSourcePaths()`、`startVideoPreview()` 和 `VideoPipeline`。
- 本地文件显示框改为不撑宽，避免挤压右侧“选择”按钮造成遮挡。
- 2026-06-26 本次验证结果：新增结构测试 1/1 通过；当前 Detector 相关结构测试 24/24 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `7866B4DC78BBFF312F561DBE76F462FDBD13A2A82197EC23F6147B61926AEABA`。

当前正在做什么：2026-06-26 已补齐 CVDS Cpp Detector 控制面板的多路本地视频在线预览入口。

上次停在哪个位置：视频源面板新增“应用本地视频”按钮；点击后会切到本地文件模式，读取“多路视频源”文本框中的每行路径，并复用现有多路实时预览线程在右侧监控画面显示多宫格预览帧。开始检测仍走原有多路 `VideoPipeline`，检测逻辑与视频流检测一致。

近期的关键决定和原因：
- 不新增本地视频专用线程或检测分支，复用已有 `configuredSourcePaths()`、`startVideoPreview()` 和多路检测管线，避免两套逻辑不一致。
- 空本地视频列表直接提示用户，避免误显示“0 路”预览。
- 2026-06-26 本次验证结果：新增结构测试 1/1 通过；当前 Detector 相关结构测试 24/24 通过；Ruff 0 个问题；C++ Release 增量编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `FED2F2E4D14FC470F60E6611EC6177599C734BA3CB605A5DD4E279B8CC19E904`。完整 `test_cpp_detector_structure.py` 中 4 条 WCS 旧目录测试仍失败，原因是 `apps/CVDS_WCS_Multi_Camera_Monitor` 当前不存在，和本次改动无关。

当前正在做什么：2026-06-26 已按当前打开软件的控制面板侧边栏宽度固定左侧栏。

上次停在哪个位置：当前打开窗口截图中侧栏分隔线约在 580 屏幕像素处，对应 Qt 侧栏 320 逻辑宽度；已将左侧栏最小宽度、最大宽度和启动默认宽度统一固定为 320，不再随窗口比例自动变宽或变窄。

近期的关键决定和原因：
- 用户要求以当前实际侧栏宽度为准，所以不再使用 `qBound(250, width * 17%, 320)` 的自动比例算法。
- 侧栏宽度属于外壳布局约束，本次不改视频源、ROI、推理参数和检测控制页内部控件。
- 2026-06-26 本次验证结果：C++ Release 编译通过；发布版签名状态 Valid，启动冒烟通过；发布版 SHA256 为 `2694BF31B0182F8BA44BABBCC9ED41D54D9B7D6D175B5DABBB619A0DB056D37F`。

当前正在做什么：2026-06-26 已同步修复左侧控制面板在最小栏宽下的宽度约束。

上次停在哪个位置：推理参数页和检测控制页不再使用 176 宽固定控件，统一回视频源可承载的 150 宽；模型文件和 OpenVINO 目录按钮改为上下排列，避免横向撑开侧栏。

近期的关键决定和原因：
- 视频源和 ROI 区域能在最小侧栏宽度下正常显示，根因是推理参数和检测控制单独用了更宽的 176 控件。
- 复用已有 `configureCompactField()` 默认 150 宽，不再新增另一套宽度规则。
- 2026-06-26 本次验证结果：C++ Release 编译通过；发布版签名状态 Valid，启动冒烟通过；发布版 SHA256 为 `E002B7C4BA70529C7AE96118FBCB0D7046E4791D5686F64A856FF1FC161C7156`。

当前正在做什么：2026-06-26 已核对并安装 Codex 插件 `ponytail`。

上次停在哪个位置：通过仓库官方说明确认 `DietrichGebert/ponytail` 是 Codex 插件，不是普通 skill；因 Windows 商店入口的 `codex.exe` 直接调用被系统拒绝访问，改用本机可执行入口 `C:\Users\lenovo\.codex\plugins\.plugin-appserver\codex.exe` 完成 `plugin marketplace add` 和 `plugin add`。

近期的关键决定和原因：
- 安装按官方 Codex 路径执行：先添加 marketplace，再安装 `ponytail@ponytail`，避免手工拷文件导致插件已落盘但未注册。
- 当前 `C:\Users\lenovo\.codex\config.toml` 已写入 `marketplaces.ponytail` 和 `plugins."ponytail@ponytail".enabled = true`，插件缓存目录为 `C:\Users\lenovo\.codex\plugins\cache\ponytail\ponytail\4.8.3`。
- 2026-06-26 本次验证结果：插件市场识别通过 1 项，插件安装通过 1 项，状态核对通过 1 项；`plugin list` 显示 `ponytail@ponytail` 为 `installed, enabled`。

当前正在做什么：2026-06-26 已修复控制面板侧边栏“推理参数”页的紧凑性和对齐问题，并同步发布版。

上次停在哪个位置：推理参数页从 `QFormLayout` 改为手工两列网格；左侧标签统一为 64 宽；视觉模型框高度从 58-78 压到 46-50；模型文件/OpenVINO 目录按钮总宽与下方控件统一；下拉框和数字框右侧蓝色按钮区从 26/24 收窄到 18。

近期的关键决定和原因：
- 问题根因不是左侧栏宽度，而是推理参数页内部控件各自撑开、标签宽度不一致、箭头按钮区域过大。
- 保持工业参数面板风格，优先统一宽度和减少纵向占用，不改检测业务逻辑。
- 2026-06-26 本次验证结果：C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `F31ABBF56F6B122EF0F0954D0EB5912C5C28823EF9912F5658A70B20BD5B6DEB`。

当前正在做什么：2026-06-25 已调整检测控制面板，并同步发布版。

上次停在哪个位置：检测控制面板中“环境自检”改为“运行环境自检”；输出目录框、选择输出目录按钮、运行环境自检按钮统一为 176 宽，并用两列网格布局保持右侧栏框对齐。

近期的关键决定和原因：
- 这块是短操作面板，输出目录框和两个按钮应统一宽度，避免看起来像三种不同层级的控件。
- 自动点击侧栏生成“检测控制”页截图未成功，当前已完成默认页截图和源码/编译/发布验证。
- 2026-06-25 本次验证结果：C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版 SHA256 为 `849C8F3672219A394940600295059CB5210AD58BF99990947C9BAFF5C6C70403`。

当前正在做什么：2026-06-25 已继续收窄 CVDS 左侧控制面板，并同步发布版。

上次停在哪个位置：左侧控制面板宽度从 320-400 继续收窄为 250-320，自动比例从 20% 左右降到 17%；海康视频流参数从横向挤在一行改为单列表单，避免 IP、端口、账号密码在窄栏里互相裁切；多路视频源占位文本改为按栏宽自动换行。

近期的关键决定和原因：
- 高 DPI 下逻辑宽度会放大，之前 360 逻辑像素在截图里仍显得很宽。
- 只调外壳宽度不够，内部长占位文本和海康横向布局会撑开左栏，所以同时收紧内部控件。
- 2026-06-25 本次验证结果：C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid；发布版预览截图已生成到 `D:\Demo\Vision\build\cvds_left_panel_narrow_preview_v3.png`；发布版 SHA256 为 `1520F8BEAA3955551CFD2C14FB4278ADED6CC12AA8486D324031C72D9DE77E53`。

当前正在做什么：2026-06-25 已优化推理参数面板 UI，并同步发布版。

上次停在哪个位置：视觉模型路径显示从单行 `QLineEdit` 改为只读可换行 `QPlainTextEdit`；推理后端、类别、执行设备、输入尺寸、预览 FPS、置信度和 NMS IoU 的目标框统一收紧为固定宽度并对齐。

近期的关键决定和原因：
- 模型路径属于长文本，单行输入框会截断；换成可换行只读文本框更适合显示长模型目录。
- 其他参数属于短选项或短数字，铺满整行会显得松散，固定短宽度更清楚。
- 2026-06-25 本次验证结果：C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过；发布版 SHA256 为 `F43C5C9C46FB481117CF9AEFBDED60493F63E15580653872FCBE616CB2D6418E`。

当前正在做什么：2026-06-25 已彻底修复海康端口 `554` 显示不完整和上下按钮压到数字上方的问题，并同步发布版。

上次停在哪个位置：海康 RTSP 端口控件从 `QSpinBox` 改为短 `QLineEdit`，使用 `QIntValidator(1, 65535)` 限制输入范围；生成 RTSP 地址时仍严格检查端口合法性，编辑为空时自动恢复为 `554`。

近期的关键决定和原因：
- 问题根因不是端口框宽度，而是 `QSpinBox` 在当前样式下自带上下按钮区域，会覆盖短数字显示区。
- 端口这种短数字不需要上下按钮，普通数字输入框更稳定，也能完整显示 `554`。
- 2026-06-25 本次验证结果：C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过；发布版 SHA256 为 `6F5F7605F7491E7C170867BF3E8E11793DCA373B34639FFD69D652ACA8807516`。

当前正在做什么：2026-06-25 已把海康端口框修复同步到发布版。

上次停在哪个位置：发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 中的 `CVDS_Cpp_Detector.exe` 已用最新构建产物替换，并使用 `CN=CVDS Local Code Signing` 重新签名；替换前发现旧发布版进程占用文件，已结束该发布版进程后完成替换。

近期的关键决定和原因：
- 只替换主程序 exe，不重建整个发布包，原因是本次只改 Qt 界面布局，依赖 DLL 和模型文件没有变化。
- 端口框修复已进入发布目录，签名状态 Valid，发布版启动冒烟通过。
- 2026-06-25 本次验证结果：发布版主程序 SHA256 为 `89C9A536061EBA4FC27F822678BCE9DA015179443017CB320B60A3484BD2F3B7`；启动 3 秒仍在运行，冒烟通过。

当前正在做什么：2026-06-25 已修复海康相机端口 `554` 这类短数字在左侧控制面板中消失的问题。

上次停在哪个位置：`hikRtspPortSpin_` 不再使用固定 64 宽度，改为按最大端口位数和 SpinBox 内部按钮区计算宽度，当前最小固定为 86；同时把 IP 输入框自适应上限从 24 字符收紧到 18 字符，避免挤占端口框空间。

近期的关键决定和原因：
- 端口不是普通文本框，SpinBox 右侧自带按钮区会占空间，64 宽在当前字体/DPI 下不足以稳定显示 `554`。
- 海康设备行采用“IP 吃剩余空间、端口固定可见短宽度”，更符合现场输入习惯。
- 2026-06-25 本次验证结果：C++ Release 编译通过，构建目录 `D:\Demo\Vision\build\cvds_cpp_detector_native_msvc` 已成功生成 `CVDS_Cpp_Detector.exe`。

当前正在做什么：2026-06-25 已把 CVDS Cpp Detector 左侧控制面板的文字框改成随内容长度自适应，并完成本机构建验证。

上次停在哪个位置：`apps/cvds_cpp_detector/src/MainWindow.cpp` 新增统一的输入框/下拉框自适应规则，并把左侧“视频源 / 推理参数 / 流量监测 / 检测控制”四组表单改成标签按内容、输入框吃剩余空间；端口短框仍保持固定短宽度。

近期的关键决定和原因：
- 这次问题的核心不只是左栏总宽度，还包括多个表单控件没有根据文字长度动态给出合理显示宽度。
- 保持现有业务逻辑不动，只改布局策略，避免再次引入预览、检测和配置保存相关风险。
- 编译失败的第一层原因是当前 PowerShell 会话没带完整 MSVC 开发环境；补用 `VsDevCmd.bat` 后暴露出唯一真实代码问题，是 `std::clamp` 混用了 `qsizetype` 和 `int`。
- 2026-06-25 本次验证结果：C++ Release 编译失败 1 次后修复通过，当前构建目录 `D:\Demo\Vision\build\cvds_cpp_detector_native_msvc` 已成功生成 `CVDS_Cpp_Detector.exe`。

当前正在做什么：2026-06-25 已把左侧控制面板调整到适合海康参数显示的宽度。

上次停在哪个位置：左侧控制面板宽度从 210-340 调整为 360-460，自动比例从 24% 调整为 26%；端口框固定为 64 宽，IP 框占剩余空间，避免右侧端口、密码、码流被裁切。

近期的关键决定和原因：
- 截图中的问题不是单个控件尺寸，而是控制面板整体上限过窄。
- 侧栏加宽后仍保留右侧监控画面为主体，但视频源配置可以完整显示。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已进一步修正左侧视频源面板窄栏下的控件裁剪问题。

上次停在哪个位置：海康设备行改为行内弹性布局，IP 框占剩余宽度，端口框固定短宽度；账号/密码、通道/码流也用等宽行内布局，避免右侧输入框被滚动条或窄面板裁掉。

近期的关键决定和原因：
- 单纯设置控件最小宽度不够，窄侧栏里三列网格会把右侧控件裁掉。
- 用“标签列 + 内容行”的布局更适合当前控制面板宽度，既保持对称也避免溢出。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已优化左侧视频源表单的海康参数输入框尺寸。

上次停在哪个位置：海康设备行中 IP 输入框加宽，端口输入框固定为短宽度；登录账号/密码、通道/码流两组控件统一间距和最小宽度，多路通道输入框保持整行宽度，整体更对齐。

近期的关键决定和原因：
- 现场最常编辑的是 IP、通道和多路通道；IP 需要更长显示空间，端口只是短数字不应占宽。
- 表单保持工业面板的对称和可读性，不改业务逻辑。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已排查并修复当前软件“卡死/假死”的清理问题。

上次停在哪个位置：Windows 事件日志没有崩溃或 Application Hang；三路运行产物在 `C:\Users\lenovo\AppData\Local\CVDS\CVDS在线包裹流量监测\runs\camera_1..3` 均写出 `flow_summary.json`，说明检测线程已结束。但进程仍占用约 775MB 私有内存，原因是 `VideoPipeline` 通过 `thread.finished -> deleteLater` 释放，线程事件循环结束后对象和 OpenVINO 模型容易滞留。已改为 `VideoPipeline::done/failed -> pipeline->deleteLater`，再退出线程。

近期的关键决定和原因：
- 这次不是模型崩溃，也不是 Windows 应用控制策略拦截；日志证据显示检测完成后资源未及时释放。
- 推理对象必须在所属线程退出前安排释放，不能等 `QThread::finished` 后再 `deleteLater`。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已修正顶部 KPI 卡片按选中 ROI 区域显示统计。

上次停在哪个位置：顶部 KPI 不再把同一相机的全部区域状态、堵包次数和告警混入当前看板；选择某个 ROI 区域后，累计包裹、区域内包裹、当前状态、堵包次数只按该区域统计。选择“多区域汇总”时才显示全部区域汇总。

近期的关键决定和原因：
- KPI 是当前关注区域的摘要，不应继续绑定主统计区域或同相机全部区域。
- 区域统计详情仍保留所有路所有区域的实时明细，顶部 KPI 则只显示当前选中的区域。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已修复重启后海康多路 RTSP 预览全部打不开的问题。

上次停在哪个位置：软件不再在启动和保存设置时删除 `hikvisionPassword`，会恢复本机上次输入的海康密码；如果视频流模式下密码为空，点击应用视频流会直接提示“海康密码不能为空”，不会再生成必然打不开的 RTSP 地址。

近期的关键决定和原因：
- 三路同时打不开不是通道 4/13/19 全坏，更符合认证信息丢失；旧逻辑主动清空密码，重启后用户没重新输入就会全部失败。
- 日志仍只显示脱敏后的 RTSP 位置，不显示账号密码。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已拆分多路检测的区域统计详情和顶部 KPI 统计口径。

上次停在哪个位置：区域统计详情现在使用所有相机的最新区域状态实时刷新，不再被点击选中的子画面过滤；顶部 KPI 单独使用 `dashboardRuntimeStates_`，检测开始后点击某个子画面时，累计包裹、区域内包裹、堵包次数和状态会映射到该子画面，没有选中时显示全局汇总。

近期的关键决定和原因：
- 区域表是明细，应实时展示所有路的区域状态；顶部 KPI 是当前观察对象，应跟随选中的子画面。
- 不再用主统计区域覆盖选中子画面的顶部统计；同一 ROI 在多路相机中会以 `camera_x / 区域名` 展示，避免看起来像只更新一条。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已修复海康多路检测时某一路因启动灰帧被误判失败的问题。

上次停在哪个位置：`VideoPipeline::readFrame()` 不再因为 RTSP 连续 4 帧低信息画面就退出检测；低信息帧会被跳过，直到读取到正常帧或用户停止检测。这样 camera_3 这类通道在重连检测阶段吐出短暂灰帧时不会直接报“视频流连续输出低信息异常帧”。

近期的关键决定和原因：
- 白屏/灰屏坏帧不能进入推理和 UI，但也不能让整路相机直接退出；正确行为是跳过坏帧并等待正常帧。
- 真实读取中断、打开失败、读取超时仍然按错误处理，不隐藏真正的连接问题。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已恢复多路 ROI 连续绘制行为。

上次停在哪个位置：修复了检测前点击多路子画面时，每点击一个 ROI 顶点就自动新建区域的问题。现在同一子画面内未闭合、已有点的 ROI 会继续作为当前区域使用，只有该子画面没有任何 ROI 时才自动准备新区域。

近期的关键决定和原因：
- ROI 绘制点击事件会在加入顶点前先触发子画面选择，所以区域选择逻辑必须识别“正在绘制但未闭合”的 ROI。
- 不清理用户已画区域、不改变计数口径，只恢复连续绘制行为。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已调整多路 ROI 绘制和子画面统计切换时机。

上次停在哪个位置：多路预览状态下点击任一子画面，会自动选中该子画面对应的 ROI 区域；如果该子画面还没有区域，软件会自动准备一个区域，不需要用户手动点击“新增区域”。点击子画面切换顶部 KPI 和区域统计详情只在检测开始后生效；检测前点击只用于 ROI 绘制归属。多路预览和多路检测的 FPS 限制保持恢复状态：预览线程约 8FPS，多路检测预览输出最多 8FPS。

近期的关键决定和原因：
- 检测前点击子画面不能改看板统计，否则会让“绘制 ROI”和“查看检测统计”两个动作混在一起。
- 多路 ROI 操作采用自动区域准备，降低现场配置步骤。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已去除多路子画面顶部半透明遮罩，让子画面拼接更自然。

上次停在哪个位置：`composeMultiCameraPreview()` 不再给每个子画面绘制顶部半透明黑条和 `camera_x` 文字，只保留普通边框和选中子画面的蓝色边框，避免用户看到类似毛玻璃的横向遮挡。

近期的关键决定和原因：
- 多路画面应优先保持原始视频连续性；子画面标签不再直接压在画面顶部，减少对时间戳和现场画面的遮挡。
- 2026-06-25 本次验证结果：当前应用相关结构测试 24/24 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已实现点击多路子画面切换统计，并修复海康视频流低信息白屏帧覆盖画面的问题。

上次停在哪个位置：`RoiPreviewLabel` 会把点击位置发给主窗口，主窗口按多宫格子画面矩形选中 `camera_x`；选中后顶部 KPI 和区域统计详情只显示该子画面的计数，选中子画面会显示蓝色边框。视频预览和检测读取都会过滤低信息异常帧，避免海康 RTSP 解码出的白屏/灰屏坏帧覆盖正常画面或进入推理。

近期的关键决定和原因：
- 点击子画面只改变看板统计范围，不改变左侧“计数口径”配置；这样不会影响各路输出文件和 ROI 配置。
- 白屏处理放在视频读取层：预览端跳过坏帧并保留上一张画面，检测端连续尝试读取后仍异常才报错，避免坏帧污染检测。
- 2026-06-25 本次验证结果：当前应用相关结构测试 23/23 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已修复多路检测启动时非主区域相机失败和 ROI 串到单路检测画面的问题。

上次停在哪个位置：多路检测拆分 ROI 后，如果某一路没有当前选择的计数口径区域，例如 `camera_2/camera_3` 没有 `main_region`，该路会自动使用内部“多区域汇总”口径运行，不再报“总计区域不存在”。多路启动前会检查 `cameraImageRects_ / cameraSourceSizes_` 是否完整，缺少子画面归属时直接提示“多路 ROI 尚未完成画面归属”，避免把全局 ROI 原样传给某一路导致串窗。

近期的关键决定和原因：
- 每路检测线程的总计区域只服务本路输出文件；主界面总计仍按左侧“计数口径”聚合显示。
- 多路 ROI 拆分必须依赖稳定的预览子画面坐标，缺少坐标时不启动检测，避免错误结果悄悄发生。
- 2026-06-25 本次验证结果：当前应用相关结构测试 21/21 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。

当前正在做什么：2026-06-25 已修复多路画面 ROI 串窗和多区域计数口径问题。

上次停在哪个位置：多路预览会记录每个 `camera_x` 子画面在多宫格中的实际位置；启动检测时会把画在对应子画面里的 ROI 转成该相机原图坐标，每路 `VideoPipeline` 只接收自己的 ROI，不再把全部区域重复画到所有子窗口。左侧 ROI 面板“主统计区域”已改为“计数口径”，可选“多区域汇总”或任一具体区域；多路检测看板会聚合各路 payload，不再只显示第 1 路计数。

近期的关键决定和原因：
- ROI 不新增复杂相机配置入口，直接根据用户在多宫格中绘制的位置判断所属子画面，减少现场操作负担。
- `__all_count_regions__` 作为内部汇总口径，不是实际 ROI；选择它时累计包裹和区域内包裹按所有计数区域汇总。
- 2026-06-25 本次验证结果：当前应用相关结构测试 21/21 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。完整结构测试中 WCS 旧删除目录相关失败仍与当前应用无关。

当前正在做什么：2026-06-25 已修复海康多路 RTSP 预览三路同时打不开的问题。

上次停在哪个位置：RTSP 预览打开时不再把 `cv::CAP_PROP_BUFFERSIZE` 放进 OpenCV FFMPEG 打开参数，改为打开成功后再设置小缓冲；每路预览失败日志会显示脱敏后的协议、IP/端口和海康通道路径，例如 `/Streaming/Channels/401`，方便判断是软件生成地址问题还是相机/NVR 通道未开放。

近期的关键决定和原因：
- 多路通道 `4,5,6` 仍按海康 `/Streaming/Channels/{通道}{码流}` 规则生成，不做隐式改写，避免把真实通道问题掩盖掉。
- 失败日志不显示账号和密码，也不打印可直接登录的完整 RTSP URL。
- 2026-06-25 本次验证结果：当前应用相关结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 主程序已替换并签名，签名状态 Valid，启动冒烟通过。完整结构测试中 WCS 旧删除目录相关 4 项仍失败，和本次当前应用修复无关。

当前正在做什么：2026-06-24 已完成当前软件长期运行提速梳理、优化和压力测试。

上次停在哪个位置：新增长期运行优化：运行日志限制为最近 800 行，避免日志窗口长期增长；RTSP 打开和检测读取设置小缓冲，减少网络波动后的旧帧堆积；检测看板统计从每帧刷新改为约 5FPS，堵包事件仍即时刷新；多路预览/检测继续保留 8FPS 预览和 10FPS 多宫格 UI 合成节流。已将重新编译后的主程序替换进 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 并签名。

近期的关键决定和原因：
- 长期卡顿风险主要来自 UI 队列和内存堆积：日志无限增长、每帧刷新看板、RTSP 旧帧缓冲、4 路画面频繁缩放合成。
- 不降低推理和计数主逻辑，只降低界面刷新与预览传输压力；堵包报警仍强制即时刷新。
- 2026-06-24 本次验证结果：当前应用结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译通过；4 路本地视频解码压力 120 秒通过，RSS 135.4MB 到 138.5MB，最大 139.4MB；程序空载稳定性 120 秒通过，工作集 53.9MB 持平、句柄 301 到 302；发布目录主程序已签名，最终发布目录 40 个文件、681,651,109 字节，临时 unsigned exe 放入发布目录后启动通过。

当前正在做什么：2026-06-24 已优化 4 路视频预览/检测时界面卡顿问题。

上次停在哪个位置：多路实时预览从“每路约 30FPS 都立即发 UI 重绘”改为“每路预览约 8FPS，主界面最多约 10FPS 合成一次多宫格”。多路检测时预览输出也自动限制为 8FPS，推理和计数逻辑不变，只降低界面帧传输和缩放重绘压力。已将重新编译后的主程序替换进 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 并签名。

近期的关键决定和原因：
- 卡顿根因是 4 路视频同时发帧时 UI 线程每秒要处理大量 QImage 传输、缩放和多宫格重绘；检测本身不应该被界面刷新拖垮。
- 不缩小预览 worker 内的原始图像尺寸，避免 ROI 坐标和原视频尺寸不一致；只限制预览帧率和 UI 合成频率。
- 2026-06-24 本次验证结果：当前应用结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译通过；发布目录主程序已替换并签名，最终发布目录 40 个文件、681,658,549 字节。构建目录 exe 启动通过，临时 unsigned exe 放入发布目录后也可启动。完整打包脚本曾因系统繁忙超时，本次依赖 DLL 未变化，因此只替换已编译主程序。

当前正在做什么：2026-06-24 已修复“应用视频流”后不显示多路小画面的问题。

上次停在哪个位置：“应用视频流”现在会按 `configuredSourcePaths()` 启动多路预览线程，而不是只启动单个 `VideoPreviewWorker`。多路通道例如 `4,5,6` 会同时打开 3 路预览，实时监控画面使用同一个多宫格合成函数显示。点击“开始检测”前会先异步停止全部预览线程，再启动多路检测。

近期的关键决定和原因：
- 根因是上一版只把“开始检测”改成了多路 `VideoPipeline`，但“应用视频流”的实时预览仍是单线程单通道，所以用户点应用后只能看到一路。
- 多路预览与多路检测共用画面合成缓存和 `composeMultiCameraPreview()`，避免两套不同显示逻辑。
- 2026-06-24 本次验证结果：当前应用结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译、便携包生成和签名通过；发布包大小 681,650,597 字节。构建目录 exe 启动通过，临时 unsigned exe 放入发布目录后也可启动。

当前正在做什么：2026-06-24 已修复海康多路通道填写 `4,5` 后仍使用旧默认通道的问题。

上次停在哪个位置：视频流模式下启动检测时不再回落读取 `sourceEdit_` 里的旧单路 RTSP；会直接按当前海康配置重新生成源列表。填写“多路通道”时只运行这些通道，例如 `4,5` 只生成 4、5 通道；留空时才运行当前单通道。点击“应用视频流”时，如果填了多路通道，会用第一路通道做实时预览，避免旧通道画面误导。

近期的关键决定和原因：
- 根因是旧的 `sourceEdit_` 保存了上一次“应用视频流”的单通道 RTSP，例如 6 通道；启动检测时多路通道没有强制覆盖这个旧地址。
- 视频流模式下源列表必须来自海康通道配置，而不是历史路径缓存；本地文件模式才允许读取 `sourceEdit_`。
- 2026-06-24 本次验证结果：当前应用结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译、便携包生成和签名通过；发布包大小 681,647,525 字节。构建目录 exe 启动通过，临时 unsigned exe 放入发布目录后也可启动。

当前正在做什么：2026-06-24 已基于海康通道切换逻辑完善多路视频在线检测。

上次停在哪个位置：视频源面板新增“多路通道”，填写 `1,2,3` 会按当前海康 IP、账号、密码、端口、主/子码流和传输协议自动生成多路 RTSP；仍保留“多路视频源”逐行填写完整本地文件或 RTSP 的能力。检测启动后每路独立 `VideoPipeline`，实时监控画面合成为多宫格，输出写入 `camera_1`、`camera_2` 等子目录。发布包已重新生成并签名到 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed`。

近期的关键决定和原因：
- 多路海康不要求用户手写 RTSP，直接复用单通道的 `/Streaming/Channels/{channel}{stream}` 规则，避免通道切换逻辑和多路逻辑分裂。
- 手写多路视频源优先级高于海康多路通道，方便混合本地文件或非海康 RTSP 测试；海康多路通道留空时继续按单通道运行。
- 2026-06-24 本次验证结果：当前应用结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译、便携包生成和签名通过；发布包大小 681,645,477 字节。构建目录 exe 启动通过，临时 unsigned exe 放入发布目录后也可启动，说明发布 DLL 完整；签名发布 exe 仍会被本机 Smart App Control 对本地自签名证书的策略拦截。

当前正在做什么：2026-06-24 已修复堵包解除后红色报警残留，并给 `apps/cvds_cpp_detector` 增加多路视频在线检测基础能力。

上次停在哪个位置：堵包状态变化时会强制刷新预览帧，`IO_JAM_OFF` 后会同步清空红色 ROI/报警边框状态；视频源栏新增“多路视频源”，每行一路本地视频或 RTSP 地址，启动后每路使用独立纯 C++ `VideoPipeline` 线程检测，预览画面合成为多宫格，输出写入 `camera_1`、`camera_2` 等子目录。发布包已重新生成到 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 并签名。

近期的关键决定和原因：
- 不启用旧 `WcsInferenceManager`，因为它仍带进程式管理思路；多路检测直接复用当前纯 C++ `VideoPipeline`，避免回到 Python/worker 路线。
- 堵包解除后红框残留的主要风险来自预览帧降频：状态已经解除，但画面仍停在上一张带红框的预览帧；现在堵包开/关事件都会强制推送一帧新预览。
- 2026-06-24 本次验证结果：当前应用结构测试 20/20 通过，Ruff 0 个问题，C++ Release 编译、便携包生成和签名通过；发布包大小 681,641,319 字节。签名发布 exe 被 Smart App Control / Code Integrity 拦截，事件显示未满足 Enterprise signing level；同一构建 exe 可启动，临时复制 unsigned exe 到发布目录后也可用发布 DLL 启动，说明程序和发布包运行库正常，阻塞点是本机应用控制策略不认可本地自签名发布 exe。

当前正在做什么：2026-06-24 已完成 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 发布包 DLL 精简。

上次停在哪个位置：发布包重新生成并签名，启动冒烟通过；总大小从最初约 2.76GB 降到 681,621,760 字节，DLL 合计 639,747,856 字节。当前保留 Qt、OpenCV、OpenVINO CPU/GPU/AUTO、TensorRT `nvinfer_11.dll` 和必要 MSVC/图形运行库；已排除 TensorRT builder resource、nvonnxparser、OpenVINO NPU、auto-batch、hetero、openvino_c、Python、Torch、Ultralytics、worker、`.pt`、`.onnx` 等运行端无关文件。

近期的关键决定和原因：
- 当前机器有 Intel GPU 和 NVIDIA GPU，但没有 NPU；OpenVINO 发布包只保留 `AUTO / CPU / GPU`，界面也同步移除 NPU，避免用户选到缺失插件。
- TensorRT 真后端必须保留 `nvinfer_11.dll`，这是当前发布包最大的 DLL，继续删除会破坏 NVIDIA GPU 推理。
- 2026-06-24 本次验证结果：当前应用结构测试 18/18 通过，Ruff 0 个问题，C++ Release 编译、便携包生成、签名和启动冒烟通过；启动到可响应约 3.8 秒。

当前正在做什么：2026-06-24 已梳理并修正 `apps/cvds_cpp_detector` 推理参数中的执行设备选项。

上次停在哪个位置：界面不再把 OpenVINO 的 `GPU` 和 NVIDIA 的 `CUDA` 混在同一个固定列表里；执行设备会随推理后端动态切换。OpenVINO 显示 `AUTO / CPU / OpenVINO GPU（Intel） / NPU`，TensorRT 显示 `NVIDIA CUDA GPU 0`。

近期的关键决定和原因：
- 本机有 Intel Arc Pro Graphics 和 NVIDIA GeForce RTX 4050 Laptop GPU；OpenVINO 的 `GPU` 指 Intel/OpenVINO GPU 插件，不等于 NVIDIA CUDA。
- 真正使用 NVIDIA RTX 4050 的路径是 TensorRT；TensorRT 后端现在接收设备编号并在加载 engine 前调用 `cudaSetDevice(0)`。
- 2026-06-24 本次验证结果：当前应用结构测试 18/18 通过，Ruff 0 个问题，C++ Release 编译、便携包生成、签名和启动冒烟通过。

当前正在做什么：2026-06-24 已按用户要求撤回刚才将 `apps/cvds_cpp_detector` 改成 WCS 多路系统的代码变动。

上次停在哪个位置：程序入口已恢复为单路 `MainWindow`；CMake 不再编译 `WcsMonitorWindow/WcsInferenceManager/CameraTileWidget`；发布脚本不再复制 WCS configs 和 TensorRT engine 到发布包。`D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed\CVDS_Cpp_Detector.exe` 已重新生成并签名。

近期的关键决定和原因：
- 只撤回刚才 WCS 化的改动，不做整仓库 reset，避免误伤更早的纯 C++、OpenVINO、TensorRT 改造。
- 当前应用相关结构测试 18/18 通过，Ruff 0 个问题，C++ Release 编译、便携包生成、签名和启动冒烟通过。
- 全量结构测试中 `apps/CVDS_WCS_Multi_Camera_Monitor` 相关 4 项仍失败，原因是该目录在当前工作区已处于删除状态，不属于本次撤回产生的问题。

当前正在做什么：2026-06-24 已完成 `apps/cvds_cpp_detector` 纯 C++ 重构核查和启动速度优化。

上次停在哪个位置：确认当前发布目录 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed` 的运行端只包含 Qt6、OpenCV、OpenVINO、TensorRT 和 C++ 程序依赖；没有 Python、conda、Torch、Ultralytics、worker、`.py`、`.pt`、`.onnx` 运行端文件。源码树中仍保留历史脚本和旧文档，但它们不参与当前 CMake 构建和发布包，未做删除。

近期的关键决定和原因：
- 软件打开时不再扫描 `weights` 目录寻找默认模型；模型路径为空时，只在点击开始检测时再自动寻找默认 OpenVINO 模型，避免 GUI 启动被大模型目录拖慢。
- 发布脚本清理旧 build/dist 目录改为失败即停止，不再静默残留旧 DLL；发布结束会强制检查并拒绝 `opencv_java`、Python、Torch、Ultralytics、worker 等运行端文件。
- OpenCV Java DLL 已从 CMake 运行库复制和发布脚本中排除，减少无关体积和启动加载风险。
- 2026-06-24 本次验证结果：236/236 测试通过，Ruff 0 个问题，Release 编译和便携包生成通过；`CVDS_Cpp_Detector.exe` 签名状态 Valid；热启动实测约 0.85 秒。

当前正在做什么：2026-06-24 已修复 Codex/OpenCode 在 Vision 仓库里的高频磁盘写入根因之一：项目 watcher 忽略目录不完整。

上次停在哪个位置：`opencode.json` 之前只忽略了 build、dist、venv、datasets、weights 等大目录，但还会继续盯 `audit/`、`archive/`、`.superpowers/`、`tools/downloads/` 以及 `apps/DWSVisionCountService/cache/` 等非源码高频变化目录，导致额外扫描和磁盘写入。

近期的关键决定和原因：
- 这次不碰模型、不碰分支，只修项目级 `opencode.json` watcher 范围；直接原因是问题出在 Codex/OpenCode 对非源码目录的持续监听，不是业务代码逻辑。
- 新增回归测试，强制要求 `audit/**`、`archive/**`、`.superpowers/**`、`tools/downloads/**`、`apps/DWSVisionCountService/cache/**`、`apps/DWSVisionCountService/debug/**` 必须被 watcher 忽略，防止以后配置回退。
- 2026-06-24 本次验证结果：8/8 测试通过，Ruff 0 个问题，`opencode.json` JSON 解析通过。

当前正在做什么：2026-06-24 已完成 `apps/cvds_cpp_detector` 纯 C++ OpenVINO 改造收口，并新增 TensorRT GPU 真后端；随后修复 OpenVINO YOLO 分割端到端输出检测框错误。

上次停在哪个位置：TensorRT 11.0.0.114 CUDA 13.2 Windows SDK 已下载安装到 `D:\tools\TensorRT-11.0.0.114`；用户环境变量已写入 `TENSORRT_ROOT=D:\tools\TensorRT-11.0.0.114` 和 `TRT_LIBPATH=D:\tools\TensorRT-11.0.0.114\lib`。修复后的 TensorRT/OpenVINO 便携包已生成到 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed`。

近期的关键决定和原因：
- TensorRT 运行端只支持已构建好的 `.engine/.plan`，不在软件里临时转换 ONNX；原因是 TensorRT engine 与 GPU、驱动、CUDA 和 TensorRT 版本绑定，运行端加载成品 engine 最稳。
- CMake 支持自动探测 TensorRT SDK，兼容 TensorRT 11 的 `nvinfer_11.lib` 命名，找到 CUDA 与 TensorRT 后启用 `CVDS_WITH_TENSORRT`。
- OpenVINO 后端不再硬要求单输出，会遍历全部输出并解析可用 YOLO 检测张量，适配端到端导出的检测模型。
- OpenVINO YOLO 分割模型读取同目录 `metadata.yaml`；发现 `end2end: true` 时按 `[x1,y1,x2,y2,score,class_id,mask...]` 解析，忽略 mask 系数，避免错误大框。
- 视频帧叠字不再把中文区域名传给 OpenCV `cv::putText`，改用区域 ID，避免 Hershey 字体不支持中文导致问号乱码。
- 纯 C++ 流水线已接入仓库内 C++ ByteTrack：每帧检测后调用 `tracker_.update()`，计数和堵包使用跟踪结果。
- C++ ByteTrack 已对齐 Ultralytics 关键阈值思路：低分候选用于续跟，新轨迹阈值跟随界面置信度，第二阶段低分匹配更严格，减少漏跟和串 ID。
- 目标框颜色已按流量 ROI 中心点状态切换：ROI 外黄色，进入/压线后绿色，离开后恢复黄色。
- 累计包裹数量显示延迟已处理：计数仍按每帧 trackId 首次进入 ROI 计一次，看板统计 payload 改为每帧发送，图像预览保持降频发送。
- ROI 绘制提示“当前区域”已移到画面右上角。
- `D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best.pt` 已转换为 TensorRT engine：`D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best.engine`；同名 metadata 标记 `task: segment`、`end2end: true`。
- C++ TensorRT 后端已支持多输出和 metadata 端到端解析，适配该 engine 的 `output0 [1,300,38]` 与 `output1 [1,32,256,256]`。
- 发布脚本应使用 PowerShell 7 `pwsh` 执行；Windows PowerShell 5 会误读无 BOM UTF-8 中文字符串。
- 225/225 测试通过，TensorRT 真后端 Release 编译通过；便携包内已包含 `nvinfer_11.dll`、`nvonnxparser_11.dll` 和 TensorRT 资源 DLL。
- 2026-06-24 现场报 OpenVINO `Available frontends:` 为空，根因是发布目录缺少 `openvino_ir_frontend.dll`；已补齐当前目录和新验证目录，并修复打包脚本中过宽的 `d.dll` debug 过滤。
- 2026-06-24 检测框异常已修复并重新发布；226/226 测试通过，Ruff 0 个问题，Release 编译和便携包生成通过，`CVDS_Cpp_Detector.exe` 签名状态 Valid。
- 2026-06-24 视频叠字乱码已修复并重新发布；16/16 结构测试通过，Ruff 0 个问题，Release 编译和便携包生成通过，`CVDS_Cpp_Detector.exe` 签名状态 Valid。
- 2026-06-24 C++ ByteTrack 已优化并重新发布；229/229 测试通过，Ruff 0 个问题，Release 编译和便携包生成通过，`CVDS_Cpp_Detector.exe` 签名状态 Valid。
- 2026-06-24 目标框 ROI 状态色已优化并重新发布；230/230 测试通过，Ruff 0 个问题，Release 编译和便携包生成通过，`CVDS_Cpp_Detector.exe` 签名状态 Valid。
- 2026-06-24 累计数量显示延迟、ROI 提示位置、TensorRT engine 转换和 TensorRT 多输出解析已完成；233/233 测试通过，Ruff 0 个问题，TensorRT engine 执行通过，Release 编译和便携包生成通过，`CVDS_Cpp_Detector.exe` 签名状态 Valid。

当前正在做什么：2026-06-23 已按旧会话的界面方向完成 `apps/CVDS_WCS_Multi_Camera_Monitor` 的 UI 设置优化。

上次停在哪个位置：WCS 主界面已从简单竖排改成左右分栏，顶部增加“展开/收起控制面板”，开始监测后自动收起左栏，右侧监控区优先放大；重新编译签名后离屏启动验证通过。

近期的关键决定和原因：
- `Geometry.cpp` 补上 `opencv2/imgproc.hpp`，修复 `cv::pointPolygonTest` 编译失败。
- `apps/CVDS_WCS_Multi_Camera_Monitor/CMakeLists.txt` 去掉重复编译的旧 `WcsConfig/WcsMessage/WcsTcpClient` 实现，并补上 `CameraTileWidget.h`、`CameraWorker.h`，避免链接冲突和 Qt MOC 缺失。
- `apps/CVDS_WCS_Multi_Camera_Monitor/README.md` 已补成和现状一致的 OpenVINO IR 运行约束与 WCS 信号说明，避免结构测试继续失败。
- 当前机器不需要关闭 Smart App Control；对本次本机构建验证，只要给 exe 补有效本地代码签名即可放行。
- `openvino.dll` 缺失的直接原因是构建后没有复制运行库；现已把 Qt、OpenVINO、TBB 和 OpenCV DLL 复制加入 `apps/CVDS_WCS_Multi_Camera_Monitor/CMakeLists.txt` 的 `POST_BUILD`，构建目录可以直接运行。
- `apps/cvds_cpp_detector/packaging/build_release.ps1` 已补齐 Python 环境下 OpenVINO CMake 路径的识别，便携版会自动带齐 OpenVINO DLL。
- 参考线程 `019eb0d8-adab-7693-ad64-c1dd27e12778` 中 `2.4.0` 的界面原则，WCS 界面也统一为“控制区可收起，监控区优先”的结构。

当前正在做什么：2026-06-13 已完成 Vision 仓库结构整理和本机产物清理。

上次停在哪个位置：延迟测试已迁入 `tools/diagnostics/llm_latency/`，各应用的文档和打包脚本已归入应用目录，历史标注源码和旧打包配置已迁入 `archive/`；旧发布包移入本地忽略的 `artifacts/`，可重建的 build、缓存、调试输出和重复验证包已删除，释放约 48GB。

近期的关键决定和原因：
- 当前正式发布包、模型、数据集、训练结果、虚拟环境和 `ultralytics` 源码依赖全部保留。
- vLLM 延迟测试不再保存固定口令，改为读取 `VLLM_API_KEY` 环境变量，避免敏感信息进入 GitHub。
- 发布脚本只复制各自应用的文档，避免不同产品的说明混入同一个安装包。

当前正在做什么：2026-06-13 已完成根目录未跟踪 `ultralytics/` 的来源与扫描影响检查。

上次停在哪个位置：该目录确认是 2026-04-23 从 `https://github.com/ultralytics/ultralytics.git` 克隆、后续持续更新的独立源码仓库，不是运行产物或临时下载；当前训练脚本明确依赖该路径。目录约 168MB、1437 个文件，父仓库此前未忽略，OpenCode watcher 也会扫描。现已在 `.gitignore` 和 `opencode.json` 中排除整个目录，源码和训练结果均未删除或移动。

近期的关键决定和原因：
- 保留 `D:\Demo\Vision\ultralytics` 原路径，因为 `scripts/train_yolomask_yolo26seg.py` 和项目文档将其作为可复现的本地源码依赖；只阻止父 Git 收录和 OpenCode 扫描，避免仓库膨胀与无效索引。

当前正在做什么：2026-06-12 已完成 `apps/cvds_cpp_detector` 源码复查、缺失项修复和 `CVDS_Cpp_Detector2.0` 正式发布。

上次停在哪个位置：便携目录为 `D:\Demo\Vision\dist\CVDS_Cpp_Detector2.0`，安装包为 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`。92/92 测试通过，Ruff、Python 编译、C++ Release 编译、正式 worker 环境自检、模型读取、3 帧真实推理和 GUI 隐藏启动均通过。主程序、worker 和安装包已使用 `CN=CVDS Local Code Signing` 签名，本机 Authenticode 状态为 Valid；公钥证书为 `D:\Demo\Vision\dist_installer\CVDS_Local_Code_Signing.cer`。

近期的关键决定和原因：
- 模型类别读取改为异步 QProcess；读取失败或超时会明确停止检测，不再静默切到全部类别，避免窗口假死和错误检测范围。
- RTSP 密码不写入配置，网络地址持久化前移除用户信息；运行中锁定路径、参数和 ROI 编辑，防止界面与 worker 配置不一致。
- worker 改为 onedir 发布，并取消对 PyTorch、TorchVision、NVIDIA 的整包收集；正式目录仍约 4.9GB，因为 CUDA/cuDNN 离线 GPU 动态库本身约 4GB，继续删除会破坏 GPU 推理。

当前正在做什么：2026-06-12 已修复 Windows PowerShell 配置文件被执行策略阻止的问题。

上次停在哪个位置：当前用户执行策略从默认 `Restricted` 调整为 `RemoteSigned`；Windows PowerShell 5.1 的 `profile.ps1` 成功加载，Conda 初始化正常，PowerShell 7.6.2 也正常启动。未修改配置文件内容。

近期的关键决定和原因：
- 只修改当前用户执行策略，不修改整台电脑；`RemoteSigned` 允许本地脚本，同时继续限制未解锁的网络脚本。

当前正在做什么：2026-06-12 已安装微软官方最新稳定版 PowerShell 7.6.2。

上次停在哪个位置：通过 WinGet 安装 `Microsoft.PowerShell 7.6.2.0`，`pwsh.exe` 已可直接运行；UTF-8 中文输出正常。系统自带 Windows PowerShell 5.1 保留并与新版并存，WinGet 确认没有可用的更高版本。

近期的关键决定和原因：
- 使用微软官方 WinGet MSIX 包，不替换 Windows 自带 PowerShell 5.1，避免影响依赖旧版的系统脚本。

当前正在做什么：2026-06-11 已完成 `apps/cvds_cpp_detector` 多 ROI 实时看板优化和最终验证。

上次停在哪个位置：worker 已支持严格 `regions.json`、旧 `--roi` 兼容、分区计数、分区堵包、区域 CSV/JSONL/summary、中文区域名和红色画面告警；Qt 已支持区域新增/命名/删除/绘制/保存/加载、主统计区域、KPI、区域状态表和 500ms 红色闪烁。全项目测试 80/80 通过，Ruff 和 Python 编译检查通过，C++ Release 构建、隐藏启动、示例配置复制、独立 worker 打包、自诊断和 `--regions` 参数链路均通过。

近期的关键决定和原因：
- T 型口顶部总数只读取 `total_count_region`，不把主线和分流口相加，避免重复统计。
- 未右键或回车完成的区域保留为编辑草稿，不能保存或启动；已有无效配置明确报错，不自动替换。
- Qt 继续使用 `QThread + QProcess + preview.jpg`，worker 负责检测和状态，Qt 负责看板与闪烁，不引入 Web、数据库或新检测链路。
- 发布包增加 `configs/regions.example.json` 和 Pillow 依赖；已用全新目录完成非破坏性 worker 打包验证。完整发布脚本会删除旧 build/dist 产物，因此未执行。

当前正在做什么：2026-06-09 已完成海康 DS-8864N-R8(C) 网页回放卡顿的只读排查。

上次停在哪个位置：网络 40/40 Ping 成功，平均 1.25ms；千兆网卡无错误包；8 块约 5.59TB 硬盘均正常可读写。目标 D39 主码流为 2560×1440、25fps、H.265、3072Kbps，网页默认 4×4 且电脑未安装 LocalServiceComponents。未修改设备配置，未安装软件。

近期的关键决定和原因：
- 首选处理是回放改为 1×1，并安装海康官方 LocalServiceComponents；安装软件前必须取得用户确认。
- 不直接降低主码流，因为这会影响录像清晰度；只有组件安装后仍卡，才对具体通道做受控参数对比。

当前正在做什么：2026-06-09 已完成按文本名单复制图片的 PowerShell 脚本，并修正双击入口。

上次停在哪个位置：用户应双击 `C:\Users\lenovo\Desktop\noread\双击这里开始复制图片.bat`；后台 `.ps1` 已隐藏。脚本读取 `新建 文本文档.txt`，真实名单 111 条全部唯一匹配，未自动执行复制。

近期的关键决定和原因：
- 名单中的文件名没有 `.jpg` 后缀，因此按文件主名匹配；缺失、名单重复或来源重名时直接失败，完整检查通过后才复制。
- 提供 PowerShell 正式脚本和可双击的 CMD 入口；脚本使用 UTF-8 BOM，保证 Windows PowerShell 5 正确读取中文路径。

当前正在做什么：2026-06-08 已完成 Git 对象库清理，并补充本地审计、样例数据、缓存和调试产物的忽略规则。

上次停在哪个位置：`.git` 从约 41GB 降至约 688MB；垃圾对象为 0，工作区文件未删除。新增忽略规则后正在执行最终压缩核验。

近期的关键决定和原因：
- 删除无提交仓库中不可达的旧 Git 对象和 Codex 临时快照引用；这些对象主要由构建产物和本地数据快照形成。
- `audit/`、批量验证器本地 `data/`、DWS 服务 `cache/` 和 `debug/` 不属于源码，加入 `.gitignore`，防止 Codex/Git 快照再次膨胀。

当前正在做什么：2026-06-08 已完成 DWSVisionCountService Windows 1.1.0，集成运行设置、现场图片选择、ROI 绘制、配置保存后完整重启和用户指定图标。

上次停在哪个位置：签名安装包为 `dist_installer/DWSVisionCountService_Setup_1.1.0.exe`，便携目录为 `dist/DWSVisionCountService_1.1.0_20260608_093102`；成品 GUI、EXE/安装包图标、TCP 9100 和现场 JPEG bytes 请求均已验证。

近期的关键决定和原因：
- 2026-06-08 Windows 1.1.0：GUI 新增 TCP 端口、模型目录、置信度、IoU、推理线程、JPEG reduce 和调试图设置；ROI 页支持选择现场图片、检测矩形、输送带多边形、多个忽略矩形、撤销和清空。ROI 始终保存为原图整数坐标，保存前检查范围、自相交和零面积。配置不热更新，写入 YAML 后完整重建 TCPServer、ParcelCounter 和模型后端。用户提供的蓝色图案已统一用于窗口、EXE 和安装程序。127/127 测试通过，ruff 0 个问题；签名均为 Valid。安装包 SHA256 为 `8C439FDFBA6C9B2D976F41372021B4489F237DF06DD9C2894B8A059A9ADEC042`。
- 2026-06-08 Windows 1.0.1 修复：日志初始化只在 `sys.stderr` 存在且具有可调用 `write` 方法时添加控制台输出，避免 PyInstaller windowed 模式启动崩溃；窗口标题显示版本号，打包脚本把传入版本写入发布配置，避免失败包与修复包同版本混淆。完整测试 100/100 通过，ruff 0 个问题；EXE、原生解码 DLL 和安装包签名状态均为 Valid。安装包 SHA256 为 `879C3BE8AF574BBEBA82E3D1B3A7E7C7BF80A010382874487D411FBE151E0046`。
- 2026-06-07 Windows 软件发布：新增 Tkinter 轻量 GUI，只负责启动/停止、服务状态和最近结果；检测使用独立后台线程，结果先返回 DWS 再更新界面。采用 PyInstaller onedir 和 CPU-only Torch，避免 onefile 启动解压及约 4GB CUDA 运行库。原生 OpenVINO 复测仍有 4 张计数差异，因此软件继续使用零差异的 `ultralytics_openvino`。签名后的 EXE 通过 TCP 重放 318 张真实 DWS 图片：318/318 成功，计数差异 0 张，平均总耗时 71.65ms，P50 70ms，P95 83ms，平均解码 25.24ms、推理 32.25ms。结果保存到 `DWSVisionCountService/cache/output/dws_windows_packaged_tcp_20260607.csv` 和对应 summary JSON。
- 2026-06-07 Windows 签名：`DWSVisionCountService.exe`、`dws_turbojpeg_decoder.dll`、`turbojpeg.dll` 和安装包均由 `CN=CVDS Local Code Signing` 签名，本机 Authenticode 状态全部为 Valid。安装包 260.10MB，SHA256 为 `279C151E5A6D52082560BDB75D38B8229318F1B3EBB9B58430190AF7565BEF37`；公钥证书导出到 `dist_installer/CVDS_Local_Code_Signing.cer`。
- 2026-06-07 C++ TurboJPEG 重构：没有整体重写 C++，因为现有 OpenCV 和 OpenVINO 主体本来就在原生库中执行；只替换最大瓶颈 JPEG 解码。318 张图片原生解码与 OpenCV 逐像素差异 0 张，原生解码微基准平均 27.49ms，OpenCV 平均 64.90ms。完整 INT8 OpenVINO 链路 318/318 成功，计数差异 0 张，分布仍为 0 包 11 张、1 包 292 张、2 包 15 张；平均总耗时 77.81ms，P50 76ms，P95 93ms，平均解码 29.62ms、预处理 12.96ms、推理 33.73ms。相对上一版 120.63ms 再提速 35.5%。原生 DLL 缺失或解码失败直接返回错误，不回退 OpenCV。
- 2026-06-07 全尺寸严格质量优化：生产默认继续使用 `decode_reduce_factor=1`、INT8 OpenVINO 和原有检测阈值，仅优化像素结果完全等价的预处理。318/318 成功，0 失败；与优化前逐图计数差异 0 张，分布仍为 0 包 11 张、1 包 292 张、2 包 15 张。磁盘读取在计时外，平均总耗时从 166.87ms 降到 120.63ms，提升 27.7%；P50 119ms，P95 135ms；平均解码 74.89ms、预处理 12.64ms、推理 31.65ms、后处理 0.28ms。汇总保存到 `DWSVisionCountService/cache/output/dws_full_decode_preprocess_optimized_20260607_summary.json`。
- 2026-06-07 预处理优化依据：旧实现对 ROI 先复制，再通过 NumPy 布尔索引逐像素清零，预处理约 53ms；新实现缓存组合 mask，并由 OpenCV 原生 `copyTo` 一次完成复制和掩膜，100 张微基准平均 10.69ms。随机图片在全尺寸和 reduce 坐标下均与旧实现逐像素一致，不使用降级、阈值补偿或启发式后处理。
- 2026-06-07 reduce4 最新实测：使用 `C:\Users\lenovo\Desktop\DWS` 的 318 张图片和 `D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best_int8_openvino_model`，以 `decode_reduce_factor=4` 跑完整 byte 生产链路；本地 `read_bytes()` 在计时外执行，统计范围为服务收到 bytes 后的解码、预处理、推理和后处理，不含磁盘读取、网络传输和 debug 输出。318/318 成功，0 失败；计数分布为 0 包 19 张、1 包 284 张、2 包 15 张；平均总耗时 60.42ms，P50 59ms，P95 70ms；平均解码 18.39ms、预处理 8.84ms、推理 31.73ms、后处理 0.28ms。与 `dws_desktop_smoke_20260607.csv` 原尺寸解码基线相比有 10 张计数变化，因此 reduce4 仍不作为生产默认。逐图 CSV 保存到 `DWSVisionCountService/cache/output/dws_reduce4_openvino_20260607.csv`，汇总 JSON 保存到 `DWSVisionCountService/cache/output/dws_reduce4_openvino_20260607_summary.json`。
- 2026-06-07 桌面 DWS 全量冒烟：使用 `C:\Users\lenovo\Desktop\DWS` 的 318 张真实图片和当前 INT8 OpenVINO 模型运行修复后的 benchmark；318/318 返回 `code=0`，0 失败；计数分布为 0 包 11 张、1 包 292 张、2 包 15 张，与历史质量基线一致；平均总耗时 166ms，P50 165ms，P95 188ms，平均推理 31ms，平均解码 71ms。CSV 保存到 `DWSVisionCountService/cache/output/dws_desktop_smoke_20260607.csv`，完整日志保存到同目录 `.log` 文件。
- 2026-06-07 冒烟旧链路根因：demo 缺少项目根目录导入路径、调用不存在的 `Config.load()`，并把 runner 结果当对象列表；benchmark 混用 `decode_image_bytes + count_image + count_bytes`，导致每张图片重复推理。已统一为 `ImageMeta + image_bytes -> ParcelCounter.count_bytes() -> CountResult`。
- 2026-06-07 本地验证：84/84 测试通过，ruff 0 个问题。真实 INT8 OpenVINO 模型 `D:/Demo/Vision/weights/yolo26s-seg-wds-1024-best_int8_openvino_model` 加载成功；demo 对 `test_image.jpg` 返回 `code=0,count=0,processing_time_ms=132`；benchmark 返回 `code=0,count=0,processing_time_ms=124,decode_time_ms=35,inference_time_ms=68`，CSV 保存到 `DWSVisionCountService/cache/output/smoke_benchmark_20260607.csv`。

当前正在做什么：已按粘贴需求补齐 DWSVisionCountService 生产 byte 主链路，统一为 ImageMeta + image_bytes → 内存解码 → preprocess → OpenVINO/Ultralytics 后端 → postprocess → CountResult。

上次停在哪个位置：已创建 `AGENTS.md`、项目级 `opencode.json`、`.opencode/agents/` 和 `.opencode/commands/`；当前项目启用 `codex-senior` 默认 agent 和 `searxng-public` 免费 MCP。已用临时本地 OpenCode CLI 验证配置解析和 MCP 连接通过；下一步是在桌面版 OpenCode 中重启或重新打开当前项目。
- DWSVisionCountService 新主链路验证：2026-06-05 使用项目 .venv 跑 `pytest`，67/67 通过；跑 `ruff check .`，0 个问题；用 `test_image.jpg` 做真实 bytes 烟测返回 `code=0`。TCP 协议已改为 4 字节 big-endian header 长度 + header JSON + image bytes，HTTP 只作为 byte 调试接口。

近期关键决定和原因：
- DatasetAssistant V1.0 聚焦图片批处理、标注转换、数据集划分、ONNX 推理和诊断，不再内置堵包视频制作，避免数据集工具职责发散。
- 参考 CVAT、Label Studio、LabelImg、LabelMe、X-AnyLabeling 后，只吸收适合现场单机工具的优点：格式兼容、质量检查、项目化、轻量操作、AI 可选；不引入 Docker/Web 服务、复杂账号系统或 GPL 代码。
- 独立 `apps/cvds_jam_video_synthesizer/` 作为历史工具保留在仓库中，不再作为 DatasetAssistant V1.0 的功能入口。
- 新版标注工具 v2.3 放在 `apps/cvds_annotation_tool_v2_3/`，避免和老版 `apps/cvds_annotation_tool.py` 同名冲突。
- `apps/cvds_annotation_tool_legacy/` 只保留历史单文件标注工具和早期 SAM 集成，不作为当前发布入口。
- 删除功能后必须继续跑 CTest，确保图片处理、标注 IO、数据集划分、推理诊断等核心能力不受影响。
- 发布脚本不再吞掉 Application Control / Device Guard 拦截；签名后再运行 `DatasetAssistant.exe --diagnose`，如果仍被拦截会直接失败。
- Opencode 优化结论：默认主模型设为 `team-ollama-lan/qwen3.6:latest`，轻量任务设为 `team-ollama-lan/qwen3:0.6b`；给 36B 模型限制 `context=32768`、`output=4096`，避免按 262144 超大上下文运行；用户级 `NO_PROXY` 已加入 Ollama LAN 地址，避免请求绕代理。
- OpenCode vLLM 延迟排查结论：vLLM LAN 接口本身很快，`/v1/models` 约毫秒级，短对话直接请求总耗时约 0.46 秒；慢的直接原因在 OpenCode 配置，默认曾指向本机未监听的 `127.0.0.1:8000`，且把服务端真实 `max_model_len=32768` 写成 `context=65536/output=8192`，导致大上下文时出现 `ContextOverflowError` 或长时间生成。
- OpenCode 继续排查结论：服务端当前无排队，队列时间几乎为 0；项目根目录之前没有 `.gitignore`，`build/dist/venv/.venv/datasets` 等让 OpenCode/Git 需要扫描约 18.8 万文件，其中 `dist` 约 39.5GB、`build` 约 18GB、`datasets` 约 7.4GB，这是对话前卡顿的主要本地原因。不能为了速度降低上下文能力，优化重点应放在扫描排除、代理、入口和缓存。
- OpenCode 调教方案结论：先写 `OPENCODE_TUNING.md` 方案，不直接改生效配置；长期建议用项目级 instructions、Markdown agents、commands、permissions、watcher ignore 和 MCP 清理来塑造行为。
- OpenCode 当前落地结论：方案已改为项目级生效，不改全局模型配置；默认 agent 为 `codex-senior`，保留主模型能力；`mcp-searxng-public` 作为免费实时搜索 MCP，项目内禁用 Tavily/Brave/旧 SearXNG，避免空 key、不可达或带密钥服务影响当前体验。
- OpenCode MCP 验证结论：`mcp-searxng-public@1.3.0` 为 MIT，已能在本机通过 `cmd /c npx -y mcp-searxng-public` 启动，成功列出 `search` 工具并返回搜索结果；由于首次 npx 拉包可能超过 15 秒，项目配置把 MCP timeout 设为 30 秒。
- OpenCode CLI 验证结论：直接用临时安装在 `%TEMP%` 的 `opencode-ai@1.15.13` 运行 `debug config`，退出码为 0，确认 `default_agent=codex-senior`、项目 instructions 和 watcher ignore 已生效；运行 `mcp list`，`searxng-public` 显示 connected。此前用 `npm exec opencode` 再启动 `npx` 会形成嵌套 npm，导致 MCP 假失败，不作为真实结论。
- GPU 占用排查结论：PID `33480` 为向日葵子进程，窗口名 `OrayPrivacyWnd`，并启动 `dragserver` 子进程；向日葵主程序签名有效，Defender 实时防护开启且威胁记录为空。当前未发现挖矿、大模型推理或恶意脚本证据；如果未主动使用远程控制，应先关闭向日葵并检查远程访问记录。
- DWS 批量模型检测验证工具结构结论：`run_gui.py` 是 GUI/CLI 分流入口，`run_batch.py` 是 CLI 入口，核心逻辑在 `src/dws_validator/runner.py`，推理后端在 `src/dws_validator/predictor.py`，界面在 `src/dws_validator_gui/`。
- DWS 无标签检测迭代结论：标签目录改为可选；标签目录为空或不存在时仍可批量检测，只输出预测数量、状态和信号，不计算准确率；GUI 和 README/用户说明已同步，并已重新生成 `dist/DWSBatchModelValidator/` 和 `dist/DWSBatchModelValidator.zip`。
- DWS V1.1 安装包未生成的直接原因：旧发布脚本找不到 Inno Setup 时只跳过安装包步骤，没有失败；本机 Inno Setup 安装在当前用户目录，脚本已补充该路径，并改为安装包缺失即失败。
- DWS V1.1 发布签名结论：主程序和安装包使用 `CN=CVDS Local Code Signing` 本机代码签名证书签名，并导入当前用户信任根和受信任发布者后，本机 Authenticode 校验为 Valid。正式外发仍应替换为公开受信任代码签名证书。
- DWSVisionCountService VisionRunner 流水线重构：Preprocessor.process() 统一接收 DecodedImage 对象（而非 raw numpy + warp_matrix 分散传参），返回 PreprocessOutput 封装 tensor 和变换元数据；runner 负责从 bytes 构造 DecodedImage；2026-06-05 验证 97 个测试全部通过。
- DWSVisionCountService byte 服务落地结论：生产入口改为 `ParcelCounter.count_bytes(meta, image_bytes)`；严格禁止 base64/路径/共享目录进入主链路；raw 图片不再猜尺寸，缺少 width/height/channels 直接返回 `1004`；模型缺失时服务不崩溃，health 显示 `model_loaded=false`，计数返回 `1005`。
- DWSVisionCountService 模型加载结论：当前仓库 `models/best_openvino_model/metadata.yaml` 写明 `task: detect`，后端按模型 metadata 选择 Ultralytics task；后续替换为 YOLO seg OpenVINO 模型时，应保证 metadata 中 `task: segment`。
- DWSVisionCountService 现场实测结论：2026-06-05 使用图片目录 `C:\Users\lenovo\Desktop\DWS` 和权重 `D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best_int8_openvino_model` 跑完 318 张真实 DWS 图片；318/318 返回 `code=0`，无失败；计数分布为 0 包 11 张、1 包 292 张、2 包 15 张；平均总耗时 191ms，P50 186ms，P95 218ms，平均推理耗时 35ms；结果保存到 `DWSVisionCountService/cache/output/dws_real_test_results.csv`。HTTP byte 单张实测返回 `code=0,count=1`，TCP byte 单张实测返回 `code=0,count=1`。默认 `config/config.yaml` 已切到该 INT8 OpenVINO 权重；TCP 客户端正常断开不再打印异常栈。
- DWSVisionCountService 速度优化结论：2026-06-05 从预处理和已解码路径入手优化；预处理改为先裁 ROI，再在 ROI 内做 ignore region 和 belt polygon mask，不再复制/mask 整张大图；模型加载后自动 warmup，避免首单包含 OpenVINO 编译时间；`CountResult` 新增 `decode_time_ms`，`processing_time_ms` 改为包含 JPEG 解码的真实总耗时；生产配置默认关闭 debug 图保存。318 张真实 DWS 图片复测：318/318 成功，计数分布仍为 0 包 11 张、1 包 292 张、2 包 15 张，和优化前差异 0 张；含解码平均 171ms、P50 169ms、P95 195ms；已解码路径平均 96ms、P50 96ms、P95 109ms；平均解码 74ms、预处理 63ms、推理 31ms；结果保存到 `DWSVisionCountService/cache/output/dws_real_test_results_optimized_with_decode.csv`。
- DWSVisionCountService reduce 解码结论：2026-06-05 已实现 JPEG `decode_reduce_factor` 配置，支持 1/2/4/8，并保留原图坐标还原；真实 318 张 DWS 图片用 `factor=2` 实测平均总耗时 80ms、解码 28ms、预处理 20ms、推理 30ms，但计数分布变为 0 包 16 张、1 包 287 张、2 包 15 张，和质量基线差异 9 张；由于用户要求保证检测质量，生产默认保持 `decode_reduce_factor=1`，`factor=2` 只作为可选实验配置，结果保存到 `DWSVisionCountService/cache/output/dws_real_test_results_reduce2.csv`。
- DWSVisionCountService reduce4 + debug 实测结论：2026-06-05 按用户要求用 `decode_reduce_factor=4` 跑 `C:\Users\lenovo\Desktop\DWS` 全部 318 张图，并输出 debug 图；统计耗时使用 `processing_time_ms`，不包含 debug 图绘制/保存时间。318/318 返回 `code=0`，计数分布为 0 包 19 张、1 包 284 张、2 包 15 张；和质量基线差异 10 张。剔除 debug 图输出后的平均总耗时 64ms，P50 65ms，P95 74ms；平均解码 21ms，预处理 10ms，推理 30ms；debug 图 318 张输出到 `DWSVisionCountService/debug/reduce4_20260605_v2`，CSV 保存到 `DWSVisionCountService/cache/output/dws_real_test_results_reduce4_debug_v2.csv`。同时修复 debug 文件名秒级时间戳导致重复 task_id 覆盖的问题，改为微秒级文件名。
- DWSVisionCountService 方案项落地结论：2026-06-05 已实现 NativeOpenVINOBackend、ROI 标定预览工具、2x2 tile 显式实验模式、mask overlap/partial overlap/连通分量去重，并在 health 暴露模型 metadata 中的 `task` 和 `int8`。默认配置保持 `ultralytics_openvino + decode_reduce_factor=1`。当前默认后端复测 318/318 成功，计数分布仍为 0 包 11 张、1 包 292 张、2 包 15 张，平均总耗时 179ms，P50 179ms，P95 199ms；CSV 为 `DWSVisionCountService/cache/output/dws_real_test_results_default_after_mask_overlap.csv`。原生 OpenVINO 后端 318/318 成功，平均总耗时 186ms，但与默认链路计数差异 4 张，不作为生产默认；CSV 为 `DWSVisionCountService/cache/output/dws_real_test_results_native_openvino_latest.csv`。2x2 tile + raw-mask 去重 318/318 成功，平均总耗时 647ms，但与默认链路计数差异 121 张，不作为生产默认；CSV 为 `DWSVisionCountService/cache/output/dws_real_test_results_tile2x2_maskdedup.csv`。ROI 预览图输出到 `DWSVisionCountService/debug/roi_calibration_preview.jpg`。

当前正在做什么：2026-06-13 已完成 CVDS_Cpp_Detector2.0 监控界面紧凑化、正式构建和数字签名。

上次停在哪个位置：正式版 `dist/CVDS_Cpp_Detector2.0/CVDS_Cpp_Detector.exe` 已重新打开，标题为 2.0.0；安装包已更新为 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`。

近期的关键决定和原因：
- 左侧设置栏限制为 300-360 宽并可拖动，右侧监控区优先占用剩余空间；程序默认最大化。
- 四项看板改为单行大号数值，区域表压缩；运行日志默认隐藏，通过“展开运行日志”按钮按需显示。
- 监控控件取消大尺寸硬限制，避免看板在高 DPI 或较窄窗口被裁掉。
- 完整测试 88/88 通过，代码检查 0 个问题；主程序、worker 和安装包签名均验证通过。
- 安装包 SHA256：`21808B2F161C13DEADB70FA5B3BD55BA6B3C64BC4827D8A366FB83FF2BDCD2BB`。

当前正在做什么：2026-06-13 已完成 DWS 视觉计数服务、预训练权重和项目 Markdown 文件的目录整理。

上次停在哪个位置：服务源码已迁入 `apps/DWSVisionCountService`；根目录的三个 YOLO 预训练权重已迁入本地 `weights/pretrained`；DWS 用户指南移入服务 `docs`，标注工具变更记录移入对应应用，OpenCode 调教文档移入 `.opencode/docs`。根目录只保留仓库级说明和协作记录。

近期的关键决定和原因：
- DWS 配置中的相对模型路径统一以配置文件所在目录解析，启动入口和 Windows 发布脚本不再依赖当前工作目录或固定 `D:\Demo\Vision` 路径。
- Windows 发布脚本默认使用仓库 `.venv` 和 `weights`，也允许通过参数或 `DWS_SERVICE_PYTHON`、`DWS_SERVICE_MODEL_PATH` 环境变量明确覆盖；缺失时直接失败。
- 新增根目录 `pytest.ini`，默认只收集三个正式测试区，避免误执行历史归档、第三方 `ultralytics` 和网络延迟脚本。
- 完整正式测试 243/243 通过，Ruff 0 个问题；PowerShell、OpenCode JSON 和真实模型路径校验通过。

当前正在做什么：2026-06-13 正在使用 Google Stitch MCP 重新设计 CVDS_Cpp_Detector 2.0 界面。

上次停在哪个位置：已完成 Stitch MCP 配置和官方方案生成，当前在可视化页面对比“监控画面优先”与“数据层级优先”两版深色工业监控台方案，等待用户确认最终版后再改 Qt 源码。

近期的关键决定和原因：
- 使用深石墨底色、COGY 蓝高亮、紧凑边框和小圆角，不使用渐变、玻璃或大阴影。
- 软件顶部、窗口图标、EXE 和安装包将统一使用用户提供的 `COGY氪技.jpg`，不使用 Stitch 自动生成的替代图标。
- 推荐“监控画面优先”方案：左侧配置保持窄而完整，视频区占最大面积，核心 KPI 常驻，运行日志默认隐藏并按需展开。

当前正在做什么：2026-06-14 已完成 CVDS_Cpp_Detector2.0 的 Stitch A 界面复刻、正式发布和数字签名。

上次停在哪个位置：正式便携版位于 `dist/CVDS_Cpp_Detector2.0`，安装包位于 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`；主程序、worker 和安装包签名状态均为 Valid。

近期的关键决定和原因：
- 左栏按 A 方案保持约 24%，设置按导航展开，四项 KPI、最大监控区和紧凑区域表常驻，日志默认隐藏。
- 模型、视频源和输出目录默认脱敏显示，选择后完整路径只显示 5 秒；运行逻辑始终读取控件保存的真实路径。
- 左栏字体随宽度在 11-14 像素间调整；开始检测后立即刷新顶部运行状态。
- 完整测试 247/247 通过，当前模块 Ruff 0 个问题，Release 编译和 DPI 截图验收通过。
- 安装包 SHA256：`AC9DF17B922D509F9826A0231A53CFDA03FF852CD4DCD7F979BD7CF7D49FD57D`。

当前正在做什么：2026-06-14 已完成 CVDS在线包裹流量监测 2.0.0 的多格式推理、海康视频流、区域详情和 Stitch A 功能对齐升级。

上次停在哪个位置：正式便携版位于 `D:\Demo\Vision\dist\CVDS_Cpp_Detector2.0`，安装包位于 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`；主程序、worker 和安装包 Authenticode 状态均为 Valid。

近期的关键决定和原因：
- 模型选择归入推理参数，统一支持 PT、ONNX 和 OpenVINO；环境自检同步检查 ONNX Runtime 与 OpenVINO。
- 视频源只保留本地文件和海康视频流；海康采用官方 RTSP 通道规则，支持主/子码流、TCP/UDP 和异步连接测试。
- 显式设备不可用时直接失败；worker 禁止在线自动安装，ONNX/OpenVINO 从元数据明确读取任务。
- 区域统计详情恢复为可见表格和空状态；切换视频来源时隐藏无关设置，监控画面继续保持最大。
- 262/262 测试通过，Ruff 0 个问题；PT、ONNX、OpenVINO 各完成 1 帧真实推理。
- 安装包 SHA256：`1DE351E4037A02EE6DDE9D673E9571C1828BDDBB35B9F05AAE5B2566D2A14773`。

当前正在做什么：2026-06-15 已完成 CVDS在线包裹流量监测 2.3.1 的路径显示和堵包秒数修复。

上次停在哪个位置：正式版已启动，便携目录为 `D:\Demo\Vision\dist\CVDS_Cpp_Detector2.0`，安装包为 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector2.0_Setup_2.3.1.exe`。

近期的关键决定和原因：
- Windows 本地路径只按文件路径处理；只有明确包含 `://` 的地址才按网络流显示，避免盘符被误识别为 URL 协议。
- 区域详情中的堵包秒数只在 `jam_active=true` 时显示，未堵包固定为 0；内部无流量计时不再冒充堵包时长。
- 区域统计详情默认收起，按需展开，继续优先保证监控画面面积。
- 263/263 测试通过，Ruff、Python 编译、C++ 构建、正式 worker 自检和 1 帧 OpenVINO 推理通过。
- 主程序、worker 和安装包签名状态均为 Valid；安装包 SHA256 为 `8D726C40555A10179157FE23EBC0A93EFAC7088704C7D5085E70349769FB7945`。

当前正在做什么：2026-06-22 已完成 CVDS在线包裹流量监测 2.4.0 的实时预览、会话 ROI 和监控画面最大化升级。

上次停在哪个位置：正式便携版位于 `D:\Demo\Vision\dist\CVDS_Cpp_Detector2.0`，安装包位于 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector2.0_Setup_2.4.0.exe`。

近期的关键决定和原因：
- 点击“应用视频流”后由独立线程立即读取并显示实时画面，不需要先开始模型检测；相机异常有 3 秒打开/读取超时，不阻塞界面。
- 开始检测前完整停止预览线程，再由检测 worker 接管视频源，避免同一相机被两个任务重复读取。
- 流量 ROI 和检测 ROI 仅在本次会话有效；启动时不读取默认 `regions.json`，也不从 `QSettings` 恢复检测 ROI。
- 顶部增加控制面板展开/收起按钮；开始检测后自动收起左栏，实时监控区域自动使用全部剩余空间。
- 266/266 测试通过，Ruff、Python 编译和 C++ Release 编译通过。
- 主程序、worker 和安装包签名状态均为 Valid；安装包 SHA256 为 `287BDA1CBD0CB982C7F379C62337099D8C2C61F392F5E40C14532D8F6D2C18C7`。

当前正在做什么：2026-06-22 已完成 CVDS在线包裹流量监测 2.4.1 的视频通道切换卡死修复。

上次停在哪个位置：Windows Application Hang 与 WER 日志确认旧版在切换海康通道时由界面线程同步等待 RTSP 预览线程，导致窗口消息循环停止。现已改为异步停止旧预览、只保留最后一次通道请求、旧线程退出后自动连接新通道。

近期的关键决定和原因：
- 通道切换和开始检测都不再在界面线程调用 `QThread::wait()`；仅软件退出时等待线程安全结束。
- 切换开始后立即拒绝旧预览帧，避免旧画面覆盖新通道；连续点击时只连接用户最后选择的通道。
- 修复版本升级为 2.4.1；267/267 测试通过，Ruff、Python 编译和 C++ Release 编译通过。
- 正式便携版位于 `D:\Demo\Vision\dist\CVDS_Cpp_Detector2.0`，安装包位于 `D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector2.0_Setup_2.4.1.exe`。
- 主程序、worker 和安装包签名状态均为 Valid；安装包 SHA256 为 `85A6BFF6FE2DAFF5AD49018ABD71FE3B33C69A7E18E63D6815EDCC1F9C950AE5`。
- 本机 Smart App Control 不认可本地自签名证书，正式签名程序被系统策略阻止启动；未降低或修改系统安全策略。
