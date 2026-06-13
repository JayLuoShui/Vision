# CVDS 包裹堵塞视频合成工具

这是一个 Windows 桌面 GUI 工具，用于把正常包裹输送视频转换成 synthetic/simulated 堵塞视频。

主要输出：

- `synthetic_frames/`：合成帧序列。
- `output/jam_video.mp4`：合成视频。
- `output/jam_segments.json`：堵塞片段标注，带 `synthetic/simulated` 标记。
- `output/jam_segments.csv`：堵塞片段表格，带 `synthetic/simulated` 标记。
- `project.json`：项目保存文件。

当前整帧冻结逻辑：

1. 随机或手动选择一个冻结帧。
2. 按设置时长连续复制这一帧，形成画面静止。
3. 原视频后续帧接在冻结段后面继续播放。
4. 因为是插入冻结段，输出视频时长会变长。

源码启动：

```powershell
.\.venv\Scripts\python.exe -m cvds_jam_video_synthesizer
```

打包：

```powershell
powershell -ExecutionPolicy Bypass -File .\apps\cvds_jam_video_synthesizer\packaging\build_release.ps1
```

安装包：

```powershell
iscc .\apps\cvds_jam_video_synthesizer\packaging\make_installer.iss
```
