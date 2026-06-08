# 主文件最小改动说明

## 总览

整个 SAM 集成只需要在历史主文件 `apps/cvds_annotation_tool_legacy/cvds_annotation_tool_v2.py` 中做 **3 处** 修改,
其他全部封装在 `apps/cvds_annotation_tool_legacy/sam_integration.py` 中。

如果你的主文件不叫 `cvds_annotation_tool_v2.py`,请同步修改
`apps/cvds_annotation_tool_legacy/sam_integration.py` 末尾的 `from cvds_annotation_tool_v2 import ...` 两处。

---

## 修改 1:文件顶部 import

在原有 import 后面追加一行:

```python
from sam_integration import install_sam_into_main_window
```

---

## 修改 2:MainWindow.__init__ 末尾

在 `MainWindow.__init__` 的末尾(`self.update_defect_meta()` 这一行之后)
追加一行,完成 SAM 整合:

```python
self.sam_integration = install_sam_into_main_window(self)
```

完整片段(改后):

```python
def __init__(self) -> None:
    super().__init__()
    # ...原有所有代码不变...
    self.statusBar().showMessage(self.device_text())
    self.setup_shortcuts()
    self.restore_settings()
    self.reload_labels(write_yaml=False)
    self.update_defect_meta()
    # ↓ 新增这一行
    self.sam_integration = install_sam_into_main_window(self)
```

---

## 修改 3(可选):requirements

确保环境里有 ultralytics(你应该已经有了,因为 YOLO 也用它):

```
ultralytics >= 8.1.0   # SAM 支持
```

第一次使用时,ultralytics 会自动从官方下载 `mobile_sam.pt`(约 40MB)
到当前工作目录。也可以提前下载放到 `weights/` 文件夹。

---

## 使用流程

1. 启动程序,在左侧"SAM 半自动分割"组里选择权重(默认 `mobile_sam.pt`)
2. 点"加载 / 重载 SAM"(可选,首次使用 SAM 模式时也会自动加载)
3. 按 **Alt+S** 切换到 SAM 模式,或者在模式下拉框选择"SAM 半自动 (segment)"
4. 操作:
   - **左键拉框**:得到 mask 预览(绿色半透明区域)
   - **Shift+左键**:加正点(目标内部,绿色圆点)
   - **右键**(已有预览时):加负点(背景区域,红色圆点)
   - **回车**:接受预览,转为正式标注
   - **Esc**:取消当前预览
   - 切到其他模式即退出 SAM

## 注意事项

### 性能

- MobileSAM 在 GPU 上每次推理 50-100ms,CPU 上 500ms-1s
- SAM2-Tiny 在 GPU 上 100-200ms,精度比 MobileSAM 略高
- 如果用 CPU,建议只用 MobileSAM
- 同一张图反复 prompt 时,ultralytics 会自动复用 image embedding,
  所以第二次起会快很多

### 显存

- MobileSAM:<1GB
- SAM2-Tiny:~1.5GB
- SAM ViT-B:~4GB
- 如果同时加载 YOLO + SAM,显存占用会叠加。可以点"加载 / 重载 SAM"
  之外的方式释放(目前只提供主动 shutdown,在主窗口关闭时自动调用)

### 输出

- SAM 输出的 polygon 经过 Douglas-Peucker 简化,顶点数通常 20-80
- 落入 `self.canvas.annotations` 后,与你手画的 polygon 完全等价,
  可以拖拽顶点、修改类别、删除等
- YOLO 训练时会被写成 `polygon` 格式的 segment label
  (与你已有的"目标分割"模式输出一致)

### 与缺陷模式的协同

当前实现:SAM 默认输出到主标注(`annotations`)。
如果想让 SAM 也服务于缺陷标注,只需在 `SamIntegration.activate(for_defect=True)`
调用即可——目前留作扩展点,你可以加一个 checkbox 控制。
