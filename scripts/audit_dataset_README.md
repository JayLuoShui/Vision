# YOLO 数据集审计工具

`audit_dataset.py` 用于检查 YOLO 检测数据集中的三类问题：

- 包裹框面积异常过大，可能把背景、平台或滚筒当成包裹。
- 空标签图片太少，模型缺少“没有包裹”的负样本。
- 同一视频或同一文件名前缀的相邻帧被分到 train/val/test，导致评估泄漏。

## 运行示例

```powershell
conda run -n yolo26 python .\scripts\audit_dataset.py `
  --dataset .\datasets\cvds_annotation_yolo_labeled_20260508 `
  --output .\audit\cvds_annotation_yolo_labeled_20260508 `
  --large-threshold 0.2 `
  --huge-threshold 0.4 `
  --sample-empty 5000
```

## 常用参数

```text
--dataset            YOLO 数据集根目录，内部应有 images/ 和 labels/
--output             审计输出目录，所有文件都写到这里
--large-threshold    大框阈值，默认 0.2
--huge-threshold     严重大框阈值，默认 0.4
--sample-empty       随机抽样空标签图片数量，默认 5000
--group-mode         video-id、prefix、regex、none，默认 video-id
--group-prefix-parts prefix 模式取文件名前几个下划线片段，默认 2
--group-regex        regex 模式使用的正则，优先取第一个捕获组
```

## 输出内容

```text
bbox_area_stats.csv
dataset_quality_report.md
group_split_leakage.csv
group_split_suggestion.csv
large_bbox_over_20/
large_bbox_over_40/
negative_samples/
```

`large_bbox_over_20/` 和 `large_bbox_over_40/` 里会复制原图、标签，并生成带框可视化图。

## 注意

工具只读取原始数据集，不会移动、删除或改写原数据。
