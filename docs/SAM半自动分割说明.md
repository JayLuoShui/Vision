# SAM 半自动分割说明

SAM 是可选增强能力。没有 SAM 权重或 AI 环境时，基础手工标注仍可使用。

使用方法：

1. 选择 SAM 权重，或填写官方权重名如 `mobile_sam.pt`。
2. 点击“加载 / 重载 SAM”。
3. 按 `Alt+S` 进入 SAM 模式。
4. 左键拉框生成预览，Shift+左键添加正点，右键添加负点。
5. `Enter` 接受为目标 polygon，`Ctrl+Enter` 接受为当前目标缺陷 polygon。
6. `Esc` 取消当前 SAM 预览。
