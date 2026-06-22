# CVDS在线包裹流量监测发布说明

## 已移除的本机依赖

- 不再默认调用开发机 Python。
- 不再依赖用户安装 conda、Ultralytics、PyTorch、Qt 或 OpenCV。
- 不再从当前工作目录找模型和输出目录。
- 输出默认写入用户本机 `%LOCALAPPDATA%/CVDS/CVDS在线包裹流量监测/runs/`。

## 发布包内容

- `CVDS_Cpp_Detector.exe`：Qt 主程序。
- `runtime/cvds_detector_worker.exe`：Python 推理 worker。
- `configs/bytetrack.yaml`：ByteTrack 跟踪配置。
- `configs/regions.example.json`：主线、左右分流口的多 ROI 示例。
- `weights/`：默认模型目录。
- `docs/`：用户说明、部署说明、故障排查。
- Qt、OpenCV 和 VC++ 运行所需 DLL。

## 生成安装包

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

生成结果：

- `dist/CVDS_Package_Flow_Detector/`
- `dist_installer/CVDS_Package_Flow_Detector_Setup_<version>.exe`

## 干净 Windows 验证

1. 在 Windows 10/11 64 位电脑安装生成的 Setup。
2. 启动后点击“环境自检”。
3. 在“推理参数”选择 PT、ONNX 模型文件或 OpenVINO 模型目录。
4. 在“视频源”选择本地文件，或配置海康相机视频流。
5. 设备选择“自动”，或按模型格式明确选择 NVIDIA、Intel GPU/NPU；不可用时会直接报错。
6. 检查看板 KPI、区域状态表和堵包红色闪烁。
7. 检查用户 AppData 的 `runs` 目录是否生成 `regions.json`、视频、CSV、汇总 JSON 和 `jam_signals.jsonl`。
