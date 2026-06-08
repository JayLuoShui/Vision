# CVDS AI 辅助 YOLO 标注工具 v2.3 发布说明

## 构建

构建前请先关闭正在运行的同名 exe，否则 Windows 会锁住 Qt DLL，导致旧发布目录无法替换。

基础版：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\cvds_annotation_tool\build_release.ps1
```

AI 版：

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\cvds_annotation_tool\build_release.ps1 -IncludeAI
```

## 输出

基础版：

- `dist/CVDS_Annotation_Tool_v2.3/CVDS_Annotation_Tool_v2.3.exe`
- `dist/CVDS_Annotation_Tool_v2.3.zip`

AI 版：

- `dist/CVDS_Annotation_Tool_v2.3_AI/CVDS_Annotation_Tool_v2.3_AI.exe`
- `dist/CVDS_Annotation_Tool_v2.3_AI.zip`

## 验收

- `CVDS_Annotation_Tool_v2.3_AI.exe --diagnose`
- `CVDS_Annotation_Tool_v2.3_AI.exe --window-smoke-test`
- 打开图片文件夹，手工画框或 polygon，保存 YOLO txt。
- AI 版应显示 `torch_available=true`、`ultralytics_available=true`。
