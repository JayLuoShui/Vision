# CVDS_Cpp_Detector 打包说明

`build_release.ps1` 只构建 `apps\cvds_cpp_detector` 下的 `CVDS_Cpp_Detector`。脚本会生成便携目录，并在未指定 `-SkipInstaller` 时生成 Inno Setup 安装包。

## 依赖

- Visual Studio Build Tools 2022
- CMake
- Ninja
- Qt 6 MSVC 64 位
- OpenCV C++ Release 包
- OpenVINO Runtime
- Inno Setup 6
- 可选：CUDA + TensorRT SDK

## 常用命令

```powershell
$env:QT_DIR = "C:\Qt\6.9.3\msvc2022_64"
$env:OPENCV_DIR = "C:\tools\opencv\build"
$env:OPENVINO_DIR = "D:\Demo\Vision\.venv\Lib\site-packages\openvino\cmake"
$env:TENSORRT_ROOT = "D:\tools\TensorRT-11.0.0.114"

pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

指定独立输出目录，避免覆盖已有发布包：

```powershell
pwsh -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1 `
  -DistName CVDS_Cpp_Detector_TestBuild `
  -SkipInstaller
```

## 脚本行为

1. 清理 `build\<DistName>` 和 `dist\<DistName>`。
2. 用 CMake/Ninja 编译 Release。
3. 用 `windeployqt` 收集 Qt 运行库。
4. 复制 OpenCV、OpenVINO、TBB 和可选 TensorRT DLL。
5. 只复制 `weights` 下的 OpenVINO `.xml/.bin` 模型。
6. 拦截 Python、Torch、Ultralytics、worker、PT、ONNX、无关 OpenVINO 插件等运行端残留。
7. 生成安装包。

脚本本身不负责代码签名；需要签名时在构建后调用本机 `signtool`。
