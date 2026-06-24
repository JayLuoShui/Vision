# CVDS_Cpp_Detector 打包说明

该脚本只构建 `apps\cvds_cpp_detector` 的 `CVDS_Cpp_Detector` Release 目标。成品采用纯 C++ OpenVINO Runtime。

## 依赖

- Visual Studio Build Tools 2022
- CMake
- Ninja
- Qt 6 MSVC 64 位开发包
- OpenCV C++ Release 包
- OpenVINO Runtime
- Inno Setup 6

设置 `QT_DIR`、`OPENCV_DIR`、`OPENVINO_DIR` 后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1
```

指定版本并跳过安装包：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_cpp_detector\packaging\build_release.ps1 `
  -Version 2.5.0 `
  -DistName CVDS_Cpp_Detector `
  -SkipInstaller
```

脚本会部署 Qt、OpenCV、OpenVINO、TBB 和 MSVC 运行库。模型目录只复制 OpenVINO IR `.xml + .bin` 文件。

设备支持 `AUTO / CPU / GPU / NPU`。发布包内不需要 Python 或 conda，也不包含独立推理进程。
