# RELEASE_NOTES

## 1.0.0

当前版本把命令行 DWS 批量验证工具升级为 Windows 可运行检测程序。

主要功能：

- 保留 YOLO segmentation 检测和原有 DWS 判定逻辑。
- 新增 PySide6 图形界面。
- 新增后台线程、实时进度、日志、可视化预览和取消任务。
- 新增 `--diagnose`、`--version`、`--cli`。
- 默认输出写入用户 AppData。
- 支持中文路径图片读取和可视化写入。
- 新增 PyInstaller 和 Inno Setup 发布脚本。
- 新增 OpenVINO 模型选择和推理支持，可选择 Ultralytics 导出的 `_openvino_model` 目录里的 `.xml`。

运行源码：

```powershell
python run_gui.py
python run_batch.py --diagnose
python run_batch.py --model models\yolo26s-seg.pt --images data\images --labels data\labels --device cpu
python run_batch.py --model models\yolo26s-seg_openvino_model\yolo26s-seg.xml --images data\images --labels data\labels --device cpu
```

打包：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_release.ps1
```

验证：

```powershell
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --diagnose
.\dist\DWSBatchModelValidator\DWSBatchModelValidator.exe --window-smoke-test
```

CPU/GPU 注意事项：

- CPU 模式必须可用，是默认保底运行方式。
- 自动模式会优先 CUDA，CUDA 不可用时回 CPU。
- 强制 GPU 但 CUDA 不可用时会提示中文错误，不会崩溃。
