# 当前上下文

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
