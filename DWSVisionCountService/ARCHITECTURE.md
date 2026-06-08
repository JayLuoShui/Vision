# DWSVisionCountService 架构

## 模块职责

- `app/main.py`：启动 TCP、HTTP 或双服务。
- `app/config.py`：读取配置文件并提供类型化配置。
- `app/schemas.py`：统一请求、检测和响应数据结构。
- `app/protocol.py`：实现 4 字节长度头 TCP byte 协议。
- `app/server/*`：兼容需求目录结构的服务入口。
- `app/http_server.py`：提供 HTTP byte 调试接口。
- `app/tcp_server.py`：提供 TCP byte 生产接口。
- `app/windows_app.py`：Windows GUI、服务线程控制、状态快照和发布自检入口。
- `app/utils/image_io.py`：只在内存中解码 encoded/raw image bytes。
- `app/utils/turbojpeg_decoder.py`：加载原生 DLL，并把 JPEG bytes 直接解码到 NumPy BGR 缓冲区。
- `native/turbojpeg_decoder/`：基于 libjpeg-turbo 的 C++ SIMD JPEG 解码模块。
- `app/utils/debug_draw.py`：绘制调试图。
- `app/utils/async_saver.py`：后台保存调试文件。
- `app/vision/preprocess.py`：缓存组合 mask，使用 OpenCV 原生复制完成 ROI 掩膜和 letterbox。
- `app/windows_app.py`：Windows GUI、服务生命周期、配置保存与重启。
- `app/roi_canvas.py`：图片显示和鼠标绘制交互。
- `app/roi_editor.py`：原图坐标与画布坐标转换，以及可撤销的 ROI 状态。
- `app/windows_settings.py`：运行设置和 ROI 保存前的严格校验。
- `app/vision/geometry.py`：坐标还原、IoU、多边形判断。
- `app/vision/backends/base.py`：推理后端接口。
- `app/vision/backends/ultralytics_openvino_backend.py`：第一版 OpenVINO 生产后端。
- `app/vision/backends/native_openvino_backend.py`：可选原生 OpenVINO Runtime 后端。
- `app/vision/tiling.py`：2x2 tile 实验模式窗口工具。
- `app/vision/postprocess.py`：过滤、坐标还原、box/mask overlap 去重和计数。
- `app/vision/counter.py`：完整计数链路入口。
- `scripts/roi_calibration_tool.py`：生成 ROI、皮带多边形和忽略区标定预览图。
- `packaging/windows/`：PyInstaller、发布配置和 Inno Setup 安装包定义。

## 调用关系

TCP/HTTP 接口接收 `ImageMeta + image_bytes`，调用 `ParcelCounter.count_bytes()`。`ParcelCounter` 先用 `decode_image_bytes_with_info()` 解码；全尺寸 JPEG 走 C++ TurboJPEG SIMD，其他格式和 JPEG reduce 模式保留 OpenCV。解码后调用 `Preprocessor.process()`，随后用后端 `predict()` 推理，最后由 `Postprocessor.process()` 返回可计数对象并生成 `CountResult`。当 `preprocess.mode=roi_polygon_letterbox_tile_2x2` 时，`ParcelCounter` 会把 ROI 拆成 4 个 tile，分别预处理和推理，再用 raw-mask overlap 合并候选。

Windows GUI 保存设置时不修改运行中的 `Config`。界面先构建并校验新配置，写入 `config/config.yaml`，然后停止旧 TCP 服务并用新配置重建 `TCPServer`、`ParcelCounter` 和模型后端，禁止半热更新。

Windows GUI 在独立线程中启动同一个 `TCPServer`。界面每 250ms 读取轻量状态快照，不读取图片、不执行模型逻辑；检测完成后服务先把 JSON 结果写回 DWS，再更新界面状态，因此 GUI 不进入 DWS 响应关键路径。

## 关键决定

- 生产链路只走 bytes，不走 base64、文件路径、共享目录或先落盘再读取。
- 全尺寸 JPEG 必须使用随服务部署的 TurboJPEG 原生 DLL；加载或解码失败直接报错，不使用隐式降级路径。
- Windows 发布保持 `ultralytics_openvino` 生产后端。原生 OpenVINO 虽然包更小，但真实数据仍有 4 张计数差异，不能为了软件体积牺牲质量。
- Windows 使用 PyInstaller onedir，不使用启动时临时解压的 onefile；模型和配置位于 EXE 同级目录，运行库放在 `_internal`。
- TCP 使用 4 字节 big-endian header 长度协议，避免旧的文本分隔符协议粘包歧义。
- 预处理必须 letterbox 保持比例，不直接拉伸到 1024。
- 输送带多边形和忽略区域先合成为按配置缓存的单通道 mask，再通过 `cv2.copyTo()` 一次完成 ROI 复制和掩膜；letterbox 使用 `cv2.copyMakeBorder()`，像素输出必须与旧实现完全一致。
- 后处理坐标还原统一使用 `roi_rect + scale + pad`，避免 ROI 坐标和原图坐标混用。
- 模型缺失时服务不崩溃，`/health` 返回 `model_loaded=false`，计数请求返回 `1005`。
- 生产默认保持 `ultralytics_openvino + decode_reduce_factor=1`；原生 OpenVINO、JPEG reduce 和 2x2 tile 都只作为显式实验开关，不能在计数一致性未闭合时默认启用。
- mask 去重按连通分量保留最高分候选，避免 tile 中间候选被贪心丢弃后无法传递合并。
