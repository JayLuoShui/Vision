# DWSVisionCountService

## 项目简介

这是工控机端的 DWS/WDS 包裹数量识别服务。生产链路接收 `task_id + header metadata + image_bytes`，在内存中解码图片，经过 ROI、输送带多边形和 OSD 忽略区预处理后，用 YOLO26n-seg OpenVINO 模型在 Intel CPU 上推理，最后返回 `parcel_count`。

生产主链路不使用 base64、不传图片路径、不轮询共享目录、不先落盘再读取。

## 系统架构

- `app/config.py`：读取 `config/config.yaml`。
- `app/schemas.py`：定义 `ImageMeta`、`Detection`、`CountResult` 等结构。
- `app/utils/image_io.py`：把 encoded/raw bytes 严格解码成 BGR 图像。
- `app/utils/turbojpeg_decoder.py`：调用 C++ TurboJPEG DLL 完成全尺寸 JPEG SIMD 解码。
- `native/turbojpeg_decoder/`：原生 JPEG 解码模块源码、构建配置和运行 DLL。
- `app/protocol.py`：TCP 4 字节 header 长度协议。
- `app/vision/preprocess.py`：缓存组合 mask、ROI 裁剪、OpenCV 原生掩膜复制和 letterbox。
- `app/windows_app.py`：Windows 服务控制台、运行参数设置、配置保存和完整服务重启。
- `app/roi_canvas.py`：现场图片选择和 Tkinter ROI 绘制界面。
- `app/roi_editor.py`：与界面解耦的原图/画布坐标映射和 ROI 编辑状态。
- `app/windows_settings.py`：GUI 参数、模型路径和 ROI 的严格校验。
- `app/vision/backends/ultralytics_openvino_backend.py`：第一版生产 OpenVINO 后端。
- `app/vision/backends/native_openvino_backend.py`：可选原生 OpenVINO Runtime 后端。
- `app/vision/tiling.py`：2x2 tile 实验模式窗口生成。
- `app/vision/postprocess.py`：坐标还原、面积过滤、多边形中心点过滤、box/mask overlap 去重。
- `app/vision/counter.py`：完整计数主入口。
- `app/http_server.py`：HTTP byte 调试接口。
- `app/tcp_server.py`：TCP byte 生产服务。
- `app/windows_app.py`：Windows 桌面程序、后台 TCP 服务控制和状态展示。
- `scripts/roi_calibration_tool.py`：ROI、皮带多边形、忽略区标定预览工具。
- `scripts/build_windows_release.ps1`：测试、打包、烟测、安装包生成和代码签名。

## Byte 数据流

推荐 DWS/WDS 发送 JPEG/PNG/BMP encoded bytes。raw RGB/BGR/Gray 也支持，但 raw 数据量大，现场链路压力更高。

如果上游程序已经拿到了 OpenCV BGR 图像，不要再编码成 JPEG 后走 `count_bytes()`；直接调用 `ParcelCounter.count_image(image_bgr, task_id=...)`，可以跳过 JPEG 解码时间。

`service.decode_reduce_factor` 支持 JPEG reduced decode，可选值为 `1/2/4/8`。现场 318 张图片实测中，`2` 虽然把含解码平均总耗时降到 80ms，但有 9 张计数和原图解码不一致；`4` 平均总耗时 64ms，但有 10 张计数不一致。生产默认保持 `1`，优先保证检测质量。

TCP 请求格式：

```text
[4 bytes big-endian header_json_length]
[header_json bytes, utf-8]
[image bytes]
```

TCP 响应格式：

```text
[4 bytes big-endian response_json_length]
[response_json bytes, utf-8]
```

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

当前实测使用的 OpenVINO 模型目录：

```text
../../weights/yolo26s-seg-wds-1024-best_int8_openvino_model
```

重新编译原生 JPEG 解码模块：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_turbojpeg_decoder.ps1
```

运行时必须保留 `native/turbojpeg_decoder/bin/dws_turbojpeg_decoder.dll` 和
`native/turbojpeg_decoder/bin/turbojpeg.dll`。DLL 缺失或 JPEG 解码失败会直接返回
图片解码错误，不会静默回退到较慢的 OpenCV 解码。

启动 HTTP 调试服务：

```powershell
python -m app.main --mode http --config config/config.yaml
```

启动 TCP 生产服务：

```powershell
python -m app.main --mode tcp --config config/config.yaml
```

同时启动 HTTP 和 TCP：

```powershell
python -m app.main --mode both --config config/config.yaml
```

## Windows 软件

安装包：

```text
dist_installer/DWSVisionCountService_Setup_1.0.0.exe
```

便携目录：

```text
dist/DWSVisionCountService_1.0.0_20260607_022925
```

软件启动后自动加载模型并监听 TCP `9100`。界面只负责启动、停止和显示最近结果，检测在独立后台线程运行，不参与图片解码和推理。

重新发布：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1
```

发布脚本使用 CPU-only Torch、PyInstaller onedir 和 Inno Setup，自动运行测试、签名 EXE 与原生 DLL，并发送真实 byte 请求做烟测。发布配置使用相对模型路径，换电脑后不依赖开发机的 `D:` 目录。

## HTTP 调试接口

- `GET /health`
- `POST /api/v1/parcel/count_bytes?task_id=T1&image_encoding=jpg`
- `POST /api/v1/parcel/count_json_header`，header 使用 `X-DWS-Meta`
- `GET /api/v1/config`

HTTP 只用于调试和第三方联调，生产推荐 TCP byte 协议。

## 模拟 DWS

```powershell
python scripts\tcp_client_demo.py --host 127.0.0.1 --port 9100 --image test.jpg --task_id B213705736158 --encoding jpg
```

## Benchmark

```powershell
python scripts\benchmark.py --image_dir data/test_images --config config/config.yaml --save_csv benchmark.csv
```

ROI 标定预览：

```powershell
python scripts\roi_calibration_tool.py --image C:\Users\lenovo\Desktop\DWS\sample.jpg --config config/config.yaml --output debug\roi_calibration_preview.jpg --reduce 4
```

2026-06-07 现场 318 张 DWS 图片 C++ TurboJPEG 全尺寸解码实测结果：

- 使用权重：`weights/yolo26s-seg-wds-1024-best_int8_openvino_model`
- 计数结果：0 包 11 张，1 包 292 张，2 包 15 张，0 个异常。
- 当前默认链路含 JPEG 解码总耗时：平均 77.81ms，P50 76ms，P95 93ms。
- 平均解码耗时：29.62ms。
- 平均预处理耗时：12.96ms。
- 平均推理耗时：33.73ms。
- 相对上一版 120.63ms 再提速 35.5%，逐图计数差异 0 张。
- 磁盘读取、网络传输和 debug 图输出不计入耗时。
- JPEG reduced decode `factor=2` 实测：平均总耗时 80ms，但计数差异 9 张，不作为生产默认。
- 原生 OpenVINO 后端实测：318/318 成功，平均总耗时 186ms，计数与默认链路差异 4 张，不作为生产默认。
- 2x2 tile 实验模式实测：318/318 成功，平均总耗时 647ms，计数与默认链路差异 121 张，不作为生产默认。

2026-06-07 Windows 签名软件 TCP 实测：

- 318/318 成功，计数分布仍为 0 包 11 张、1 包 292 张、2 包 15 张。
- 与生产质量基线逐图计数差异 0 张。
- 平均总耗时 71.65ms，P50 70ms，P95 83ms。
- 平均 JPEG 解码 25.24ms，平均推理 32.25ms。
- GUI、磁盘读取和网络传输不计入模型返回的 `processing_time_ms`。

## 模型导出

```powershell
python scripts\export_openvino.py --weights runs/segment/train/weights/best.pt --imgsz 1024 --out models
python scripts\export_openvino.py --weights runs/segment/train/weights/best.pt --imgsz 1024 --int8 --data parcel_seg.yaml --out models
```

## Windows 服务

第一版使用 NSSM。安装前确保 `nssm.exe` 已在 PATH 中。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1
powershell -ExecutionPolicy Bypass -File scripts\uninstall_windows_service.ps1
```

## 测试

```powershell
python -m pytest
python -m ruff check .
```

## 常见错误码

- `1001`：图片为空。
- `1002`：图片解码失败。
- `1003`：`image_len` 和实际 bytes 长度不一致。
- `1004`：raw 图片缺少 width/height/channels。
- `1005`：模型未加载。
- `1006`：推理失败。
- `1007`：后处理失败。
- `1008`：图片超过大小限制。
- `1009`：header JSON 解析失败。
- `5000`：未知异常。

## 搜索记录

- [libjpeg-turbo](https://github.com/libjpeg-turbo/libjpeg-turbo)：确认当前 OpenCV JPEG 解码链路已使用 libjpeg-turbo；局部 JPEG 解码需要额外原生接入，未用于本次低风险优化。
- [OpenVINO Preprocessing API](https://docs.openvino.ai/2025/openvino-workflow/running-inference/optimize-inference/optimize-preprocessing/preprocessing-api-details.html)：核对将预处理并入推理图的能力；本次先采用逐像素完全等价且更容易验证的 OpenCV 原生实现。

## 已完成优化和保留项

- 已使用 INT8 OpenVINO 权重，并在 `/health` 暴露 `model_int8`。
- 已实现 NativeOpenVINOBackend，但当前速度和计数一致性不优于默认后端。
- 已实现 ROI 标定预览工具。
- Windows 软件已集成运行设置、图片选择、检测矩形、输送带多边形和多个忽略矩形的交互式标定。
- 已实现 2x2 tile 实验模式，但当前现场数据过计数，不能生产默认开启。
- 已实现 mask overlap 去重和 tile raw-mask 去重。
- TCP 异步队列。
- DWS 端保持直接发送 JPEG bytes，避免 raw RGB 大流量传输。
- ROI 组合 mask 按配置缓存，使用 `cv2.copyTo()` 替代 NumPy 布尔索引清零，保持像素结果一致并减少预处理耗时。
- 全尺寸 JPEG 使用 C++ TurboJPEG SIMD 解码；318 张实测与原 OpenCV 解码逐像素完全一致。
