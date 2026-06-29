# 当前进度

## 2026-06-26

- 当前分支 `chatgpt-wcs-architecture-cleanup` 已使用 `PipelineRuntimeManager` 管理多路 `VideoPipeline`。
- 已按当前架构更新 `tests/test_cpp_detector_structure.py`，不再检查已移除的旧 WCS 独立目录。
- 已用独立 `DistName=CVDS_Cpp_Detector_GitHubBranch_20260626_Release` 构建发布包，未覆盖原 `dist` 下已有发布包。
- 验证结果：结构测试 27/27 通过，Ruff 0 个问题，C++ Release + TensorRT 构建通过，启动冒烟通过。
- 新发布包：
  - 便携目录：`D:\Demo\Vision\dist\CVDS_Cpp_Detector_GitHubBranch_20260626_Release`
  - 安装包：`D:\Demo\Vision\dist_installer\CVDS_Cpp_Detector_GitHubBranch_20260626_Release_Setup_2.4.1.exe`

## 当前源码事实

- CMake 只生成 `CVDS_Cpp_Detector` 一个可执行程序。
- 运行端使用 Qt、OpenCV C++、OpenVINO C++、可选 TensorRT C++ 和仓库内 C++ ByteTrack。
- 发布包不包含 Python、conda、Torch、Ultralytics、worker、`.pt`、`.onnx`。
- 视频预览和检测运行分开：预览用于看画面和画 ROI，开始检测后由 `VideoPipeline` 接管。
- 多路检测按 `camera_1`、`camera_2` 等编号管理输出和看板聚合。
