# DWS 视觉计数服务使用说明

## 使用方法

1. 安装后双击“DWS 视觉计数服务”。
2. 等待界面显示“服务运行中”。
3. DWS 连接软件所在电脑的 TCP `9100` 端口并发送图片 bytes。
4. 软件在同一 TCP 连接返回检测结果 JSON。
5. 关闭软件会同时停止检测服务。

## 运行设置

“运行设置”页可以修改 TCP 端口、OpenVINO 模型目录、置信度、IoU、推理线程、JPEG reduce 倍率和调试图开关。

点击“保存全部并重启服务”后，软件先校验并保存配置，再完整停止旧服务并使用新配置启动。`JPEG reduce=1` 是当前已验证的生产质量配置；修改为 `2/4/8` 后必须重新做现场质量验证。

## ROI 标定

1. 打开“ROI 标定”页并选择一张 DWS 现场图片。
2. 选择“检测矩形”，按住鼠标拖动绘制检测区域。
3. 选择“输送带多边形”，逐点单击后点击“完成多边形”。
4. 选择“忽略矩形”，拖动添加一个或多个忽略区域。
5. 可使用“撤销”或“清空当前”，完成后点击“保存全部并重启服务”。

ROI 保存为原始图片坐标，窗口缩放不会改变坐标。

## TCP 数据格式

请求：

```text
[4 字节 big-endian header JSON 长度]
[UTF-8 header JSON]
[JPEG bytes]
```

header 至少包含：

```json
{
  "task_id": "T1001",
  "image_encoding": "jpg",
  "image_len": 123456
}
```

响应：

```text
[4 字节 big-endian JSON 长度]
[UTF-8 检测结果 JSON]
```

主要结果字段：`code`、`parcel_count`、`confidence`、`processing_time_ms`、`objects`。

## 常见问题

- 界面停在“启动失败”：查看软件目录下 `logs/error.log`。
- DWS 无法连接：确认目标 IP 正确、软件显示“服务运行中”，并允许 Windows 防火墙放行 TCP `9100`。
- 模型不可用：不要移动或删除软件目录下的 `models`、`config` 和 `_internal`。
