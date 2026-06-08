# 当前上下文

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
