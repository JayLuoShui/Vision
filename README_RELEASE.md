# CVDS包裹流量检测工具发布说明

## 已移除的本机依赖

- 不再默认调用开发机 Python。
- 不再依赖用户安装 conda、Ultralytics、PyTorch、Qt 或 OpenCV。
- 不再从当前工作目录找模型和输出目录。
- 输出默认写入用户本机 `%LOCALAPPDATA%/CVDS/CVDS包裹流量检测工具/runs/`。

## 发布包内容

- `CVDS_Cpp_Detector.exe`：Qt 主程序。
- `runtime/cvds_detector_worker.exe`：Python 推理 worker。
- `configs/bytetrack.yaml`：ByteTrack 跟踪配置。
- `weights/`：默认模型目录。
- `docs/`：用户说明、部署说明、故障排查。
- Qt、OpenCV 和 VC++ 运行所需 DLL。

## 生成安装包

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

生成结果：

- `dist/CVDS_Package_Flow_Detector/`
- `dist_installer/CVDS_Package_Flow_Detector_Setup_<version>.exe`

## 干净 Windows 验证

1. 在 Windows 10/11 64 位电脑安装生成的 Setup。
2. 启动后点击“环境自检”。
3. 选择 `weights` 里的 `.pt` 模型，或手动选择模型。
4. 选择本地视频，绘制流量 ROI。
5. 设备选择“自动”，程序会优先使用 GPU；如果 CUDA 不可用，会自动切到 CPU。
6. 检查用户 AppData 的 `runs` 目录是否生成视频、CSV、JSON 和 `jam_signals.jsonl`。
