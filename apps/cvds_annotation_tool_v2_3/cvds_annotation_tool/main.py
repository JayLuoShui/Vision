from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cvds_annotation_tool import APP_VERSION
from cvds_annotation_tool.runtime_paths import RuntimePaths
from cvds_annotation_tool.services.dataset_export import export_dataset
from cvds_annotation_tool.services.dataset_quality import audit_dataset
from cvds_annotation_tool.services.diagnostics import diagnose_environment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CVDS AI 辅助 YOLO 标注工具 v2.3")
    parser.add_argument("--version", action="store_true", help="输出版本号")
    parser.add_argument("--diagnose", action="store_true", help="输出运行环境自检 JSON")
    parser.add_argument("--qapplication-test", action="store_true", help="创建 QApplication 后退出")
    parser.add_argument("--window-smoke-test", action="store_true", help="创建主窗口后退出")
    parser.add_argument("--quality-check", type=Path, help="无 UI 执行数据集质检")
    parser.add_argument("--export-dataset", type=Path, help="无 UI 导出数据集")
    parser.add_argument("--export-to", type=Path, help="导出目录")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="验证集比例")
    parser.add_argument("--zip", action="store_true", help="导出后生成 zip")
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    if args.version:
        print(APP_VERSION)
        return 0
    if args.diagnose:
        RuntimePaths().ensure_user_dirs()
        print(diagnose_environment().to_json())
        return 0
    if args.quality_check:
        report = audit_dataset(args.quality_check)
        print(json.dumps({"report_json": str(report.report_json)}, ensure_ascii=False))
        return 0
    if args.export_dataset:
        if args.export_to is None:
            parser.error("--export-dataset 需要同时提供 --export-to")
        result = export_dataset(args.export_dataset, args.export_to, val_ratio=args.val_ratio, make_zip=args.zip)
        print(json.dumps({"output_dir": str(result.output_dir), "train": result.train_count, "val": result.val_count, "zip": str(result.zip_path or "")}, ensure_ascii=False))
        return 0

    from cvds_annotation_tool import legacy_v2_3

    sys.argv = [sys.argv[0], *remaining]
    if args.qapplication_test:
        sys.argv.append("--qapplication-test")
    if args.window_smoke_test:
        sys.argv.append("--window-smoke-test")
    return int(legacy_v2_3.main())


if __name__ == "__main__":
    raise SystemExit(main())
