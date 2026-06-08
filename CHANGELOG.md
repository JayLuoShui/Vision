# CHANGELOG

## v2.3.0

- 移除本机 Anaconda Python 硬编码，不再自动跳转到 `C:\Users\shuai\...`。
- 新增运行环境自检，输出 Python、PySide6、Ultralytics、Torch、CUDA、OpenCV、Numpy、YAML、权重状态和推荐设备。
- 新增数据安全保存：YOLO 标签和缺陷 JSON 原子写入，覆盖前自动备份。
- 删除当前帧和批量删除空标签帧改为移动到 `.trash` 回收站。
- 新增数据集质检，输出 JSON 报告和类别分布 CSV。
- 新增数据集导出，支持 train/val 切分和 zip。
- 增强 AI 批量标注模式：跳过、覆盖、合并，并支持取消。
- 增强 SAM：错误写入完整日志，支持 Ctrl+Enter 接受为缺陷 polygon。
- 增强日志、错误报告复制、状态栏和快捷键帮助。
- 新增 PyInstaller 发布脚本和发布说明。
