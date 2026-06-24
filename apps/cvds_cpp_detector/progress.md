# 进度

## 2026-06-24 纯 C++ OpenVINO + TensorRT 后端

- 已完成纯 C++ 运行端核查：当前 CMake 和发布包只使用 Qt6、OpenCV C++、OpenVINO C++、TensorRT C++ 与 C++ ByteTrack；发布包不含 Python、conda、Torch、Ultralytics、worker、`.py`、`.pt`、`.onnx`。
- 已优化启动速度：窗口构造和读取设置时不再扫描 `weights` 目录，默认模型改为开始检测时再按需解析；热启动实测约 0.85 秒。
- 已加固发布脚本：旧 build/dist 删除失败会直接报错，发布结束会拒绝 `opencv_java` 和旧 Python worker 相关运行端文件残留。
- 已重新生成并签名 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed`；236/236 测试通过，Ruff 0 个问题，签名状态 Valid。
- 已将 `apps/cvds_cpp_detector` 运行推理改为 C++ 原生后端选择：OpenVINO IR 与 TensorRT engine。
- 新增 TensorRT Runtime C++ 后端，加载 `.engine/.plan`，使用 CUDA 显存、`enqueueV3` 推理，并复用 YOLO 后处理。
- 修复 OpenVINO 后端只接受单输出的问题，现在会遍历模型输出并解析可用检测张量。
- CMake 已支持自动探测 TensorRT SDK，找到 `NvInfer.h`、`nvinfer_11.lib` 和 CUDA 后启用 `CVDS_WITH_TENSORRT`。
- 已安装 TensorRT 11.0.0.114 CUDA 13.2 Windows SDK 到 `D:\tools\TensorRT-11.0.0.114`，并写入用户环境变量 `TENSORRT_ROOT` 和 `TRT_LIBPATH`。
- 已生成 TensorRT 真后端便携包 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT`。
- 225/225 测试通过，C++ Release 编译通过，便携包中已包含 `nvinfer_11.dll`、`nvonnxparser_11.dll` 和 TensorRT 资源 DLL。
- 修复 OpenVINO `.xml` 读取失败：发布包补齐 `openvino_ir_frontend.dll`，并修正打包脚本 debug DLL 过滤误删 `frontend.dll` 的问题。
- 修复 OpenVINO YOLO 分割端到端输出检测框错误：读取模型 `metadata.yaml` 中的 `end2end: true`，按 `[x1,y1,x2,y2,score,class_id,mask...]` 解析，忽略 mask 系数。
- 已重新生成并签名便携包 `D:\Demo\Vision\dist\CVDS_Cpp_Detector_TensorRT_Fixed`；226/226 测试通过，Ruff 0 个问题，TensorRT/OpenVINO Release 编译通过，主程序签名状态 Valid。
- 修复视频左上角叠字乱码：OpenCV 画面叠字改用区域 ID，不再把中文区域名交给 `cv::putText`。确认 C++ `ByteTrack.cpp` 已编译进 Release，并由 `VideoPipeline` 每帧调用。
- 优化 C++ ByteTrack：推理阶段保留 0.1 以上低分候选用于续跟，新轨迹阈值跟随界面置信度，第二阶段低分匹配 IoU 改为 0.5，且只允许刚丢 1 帧的轨迹参与低分续跟，更接近 Ultralytics ByteTrack 行为。
- 优化目标框状态色：目标中心点在流量 ROI 外时显示黄色，中心点进入或压线后显示绿色，中心点离开 ROI 后恢复黄色；ID 文字同步使用目标框颜色。
- 检查累计包裹数量：计数逻辑为 trackId 首次中心点进入 ROI 时计一次，未发现重复计数；发现看板刷新此前跟随预览帧，有显示延迟，已改为统计 payload 每帧发送、预览图仍按频率发送。
- ROI 绘制提示“当前区域”已移动到右上角，避免与检测/跟踪计数叠字重叠。
- 已将 `D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best.pt` 导出为 ONNX，并用 TensorRT 11 `trtexec` 转换为 `D:\Demo\Vision\weights\yolo26s-seg-wds-1024-best.engine`；同名 metadata 已写入端到端分割输出说明。
- C++ TensorRT 后端已增强为多输出解析，并读取 engine 同名 metadata，适配 `[1,300,38]` + `[1,32,256,256]` 的 YOLO 分割输出。

## 2026-06-11

- 已读取项目规则、上下文和经验教训。
- 已读取 ZIP 内总体开发说明、任务拆分和示例配置。
- 已完成 worker 多 ROI 配置、计数、堵包、协议和输出文件升级。
- 已完成 Qt 多 ROI 管理、主统计区域、KPI、区域状态表和 500ms 红色闪烁。
- 已保留旧 `--roi` 命令兼容，并加入发布示例配置。
- Review 修复了未闭合多边形被清空、无效配置被静默替换、堵包解除状态、堵包次数延迟和停滞秒数缺失。
- Review 继续修复了退出时线程等待、堵包事件总数同步、中文区域名绘制和发布包示例配置入口。
- 全项目测试 80/80 通过，Ruff 和 Python 编译检查通过。
- C++ Release 构建、隐藏启动、示例配置复制、独立 worker 打包、自诊断和 `--regions` 参数链路均通过。
- 完整发布脚本会删除旧 build/dist 产物，按项目安全规则未执行。

## 2026-06-12

- 完成发布前源码复查，并修复敏感信息持久化、辅助进程超时、worker 生命周期、运行中配置锁定、区域整数范围和停止时堵包清理。
- 模型类别读取改为异步；失败或超时会阻止检测启动。
- 发布脚本支持独立 `DistName`、onedir worker、命令失败检查和可选跳过安装包。
- 正式生成 `dist/CVDS_Cpp_Detector2.0` 和 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`。
- 92/92 测试通过；C++ Release、环境自检、模型读取、真实推理和 GUI 启动通过。

## 2026-06-14

- 按 Stitch A“监控画面优先”方案完成 1:1 比例复刻：左栏约占 24%，四项 KPI 常驻，监控区最大，区域表紧凑，日志默认隐藏。
- 左栏设置改为点击导航后展开；底部只保留开始和停止，环境自检移入“检测控制”。
- 模型、视频源和输出目录默认只显示简短名称；文件选择后完整路径仅短暂显示 5 秒。
- 左栏宽度随窗口尺寸重算，字体随实际宽度在 11-14 像素间调整。
- Review 修复了开始检测后顶部状态未立即切换为“正在监测”的问题。
- 完整测试 247/247 通过，当前模块 Ruff 0 个问题，C++ Release 编译和 DPI 截图验收通过。
- 正式主程序、worker 和安装包签名状态均为 Valid；安装包 SHA256 为 `AC9DF17B922D509F9826A0231A53CFDA03FF852CD4DCD7F979BD7CF7D49FD57D`。
- 完成在线包裹流量监测升级：模型选择移入推理参数，统一支持 PT、ONNX、OpenVINO；视频源收敛为本地文件和海康视频流。
- 海康视频流支持 IP、RTSP 端口、账号密码、通道、主/子码流、TCP/UDP、异步连接测试；切换来源时只显示当前相关设置。
- 顶栏补齐来源、通道、时间、版本和系统状态；区域统计详情恢复可见表格、空状态和多区域运行数据。
- 环境自检新增 ONNX、ONNX Runtime、OpenVINO；正式 worker 禁止 Ultralytics 在线自动安装，并从 ONNX/OpenVINO 元数据明确读取任务。
- 262/262 测试通过，Ruff 0 个问题，Python 编译、PowerShell 语法、C++ Release 编译通过。
- PT、ONNX、OpenVINO 各完成 1 帧真实推理；正式主程序、worker 和安装包签名状态均为 Valid。
- 正式便携版为 `dist/CVDS_Cpp_Detector2.0`，安装包为 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.0.0.exe`，SHA256 为 `1DE351E4037A02EE6DDE9D673E9571C1828BDDBB35B9F05AAE5B2566D2A14773`。

## 2026-06-15

- 修复 Windows 本地视频、模型和输出目录被误显示为网络视频流的问题。
- 修复未发生堵包时区域堵包秒数仍增长的问题。
- 区域统计详情改为默认收起、按需展开。
- 263/263 测试通过，代码检查、编译、正式 worker 自检和真实 OpenVINO 单帧推理通过。
- 正式版本升级为 2.3.1；主程序、worker 和安装包签名均为 Valid。
- 安装包为 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.3.1.exe`，SHA256 为 `8D726C40555A10179157FE23EBC0A93EFAC7088704C7D5085E70349769FB7945`。

## 2026-06-22

- “应用视频流”改为立即启动独立实时预览，不再等待开始检测。
- 预览画面出现后可直接绘制 ROI；开始检测前会停止预览，避免相机被重复读取。
- ROI 改为本次会话有效，软件重启不再恢复历史流量 ROI 和检测 ROI。
- 控制面板增加展开/收起按钮，开始检测后自动收起，让实时监控画面占满可用区域。
- 266/266 测试通过，Ruff、Python 编译和 C++ Release 编译通过。
- 正式版本为 2.4.0；主程序、worker 和安装包签名均为 Valid。
- 安装包为 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.4.0.exe`，SHA256 为 `287BDA1CBD0CB982C7F379C62337099D8C2C61F392F5E40C14532D8F6D2C18C7`。

## 2026-06-22 通道切换卡死修复

- 从 Windows Application Hang 和 WER 日志定位到：切换通道时界面线程同步等待旧 RTSP 线程，导致窗口消息循环停止。
- 视频预览切换改为异步串行，只执行最后一次通道请求；旧预览帧立即失效，旧线程退出后自动连接新通道。
- 开始检测同样改为等待预览异步退出后自动启动，界面线程只在软件关闭时等待线程收尾。
- 修复版本升级为 2.4.1。
- 267/267 测试通过，Ruff、Python 编译和 C++ Release 编译通过。
- 主程序、worker 和安装包签名状态均为 Valid。
- 安装包为 `dist_installer/CVDS_Cpp_Detector2.0_Setup_2.4.1.exe`，SHA256 为 `85A6BFF6FE2DAFF5AD49018ABD71FE3B33C69A7E18E63D6815EDCC1F9C950AE5`。
- 本机 Smart App Control 拒绝本地自签名程序启动；签名本身校验有效，未修改系统安全策略。
