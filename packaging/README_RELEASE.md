# CVDS 发布打包说明

本目录用于生成 Windows 安装包。发布包内包含 Qt、OpenCV、Python worker、模型、配置和文档，终端用户不需要安装 Python、Qt、OpenCV 或 conda。

## 构建

1. 安装开发机依赖：Visual Studio Build Tools、CMake、Ninja、Qt 6、OpenCV、Inno Setup。
2. 设置可选环境变量：`QT_DIR` 指向 Qt 的 msvc 64 位目录，`OPENCV_DIR` 指向 OpenCV CMake 包目录，`INNO_SETUP` 指向 `ISCC.exe`。
3. 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

输出目录：

- `dist/CVDS_Package_Flow_Detector/`
- `dist_installer/CVDS_Package_Flow_Detector_Setup_<version>.exe`

## worker 依赖

默认按 `requirements-worker.txt` 安装 CUDA 版 PyTorch worker。运行时优先使用 GPU；如果当前机器 CUDA 不可用，worker 会自动切到 CPU，并在日志里说明实际设备。
