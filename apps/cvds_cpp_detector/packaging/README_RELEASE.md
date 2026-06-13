# CVDS 发布打包说明

本目录用于生成 Windows 安装包。发布包内包含 Qt、OpenCV、Python worker、模型、多 ROI 示例配置和文档，终端用户不需要安装 Python、Qt、OpenCV 或 conda。

## 构建

1. 安装开发机依赖：Visual Studio Build Tools、CMake、Ninja、Qt 6、OpenCV、Inno Setup。
2. 设置可选环境变量：`QT_DIR` 指向 Qt 的 msvc 64 位目录，`OPENCV_DIR` 指向 OpenCV CMake 包目录，`INNO_SETUP` 指向 `ISCC.exe`。
3. 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

常用参数：

```powershell
# 指定版本和独立输出名称，不生成安装包
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1 `
  -Version 2.0.0 `
  -DistName CVDS_Package_Flow_Detector_2.0 `
  -SkipInstaller

# 直接复用已安装完整 worker 依赖和 PyInstaller 的 Python 环境
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1 `
  -WorkerPythonExe D:\PythonEnvs\cvds\Scripts\python.exe `
  -ReuseWorkerEnvironment
```

未传 `WorkerPythonExe` 且未使用 `ReuseWorkerEnvironment` 时，脚本仍会创建干净的 worker 虚拟环境。传入 `WorkerPythonExe` 后会直接使用该环境，不再新建 venv，也不会改动该环境的依赖。

输出目录：

- `dist/CVDS_Package_Flow_Detector/`
- `dist_installer/CVDS_Package_Flow_Detector_Setup_<version>.exe`

`DistName` 会同时决定 `build/<DistName>/`、`dist/<DistName>/` 和安装包基础名称。`SkipInstaller` 只生成发布目录，不查找或调用 Inno Setup。

## worker 依赖

默认按 `requirements-worker.txt` 安装 CUDA 版 PyTorch worker。运行时优先使用 GPU；如果当前机器 CUDA 不可用，worker 会自动切到 CPU，并在日志里说明实际设备。
