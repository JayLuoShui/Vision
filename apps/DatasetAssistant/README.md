# 数据集制作助手 V1.0

面向目标检测与图像分割数据集生产的 Windows 桌面工具。

## V1.0 范围

- 工程配置创建、保存、加载。
- YOLO / COCO / VOC / mask PNG 基础导入导出。
- resize、letterbox、crop、tiling、flip、90/180/270 rotate 的图片与标注同步变换。
- train/val/test 自动划分，默认 7:2:1，固定随机种子可复现。
- ONNX Runtime 推理接口和 GPU/CPU 诊断接口。
- Qt Widgets GUI、基础 CLI、Windows 发布脚本。

## 构建

```powershell
cmake -S .\apps\DatasetAssistant -B .\build\DatasetAssistant -G Ninja -DCMAKE_PREFIX_PATH="C:/Qt/6.9.3/msvc2022_64;C:/tools/opencv/build" -DOpenCV_DIR="C:/tools/opencv/build" -DONNXRUNTIME_ROOT="C:/tools/onnxruntime-win-x64-gpu-1.23.2"
cmake --build .\build\DatasetAssistant --config Release
ctest --test-dir .\build\DatasetAssistant --output-on-failure
```

发布脚本会自动创建或复用当前用户下的 `CVDS Local Code Signing` 本机代码签名证书，并签名 build exe、发布 exe 和安装包，避免本机 Windows Application Control / Device Guard 拦截未签名程序。

## 标注同步可视化校验

```powershell
.\build\DatasetAssistant\visual_annotation_transform.exe .\build\annotation_transform_visual
```

输出目录会生成 resize、letterbox、crop、tiling、flip、90/180/270 rotate 的带框、多边形和 mask 叠加图，用于人工确认图片变换后标注仍然对齐。

## CLI

```powershell
DatasetAssistant.exe --version
DatasetAssistant.exe --diagnose
DatasetAssistant.exe --batch-process project.cvdsproj.json
DatasetAssistant.exe --split-dataset project.cvdsproj.json
```
