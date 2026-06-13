from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "apps" / "cvds_annotation_tool_v2_3"
PACKAGE_ROOT = APP_ROOT / "cvds_annotation_tool"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v23_entry_and_legacy_source_have_no_hardcoded_ai_python():
    legacy = read(PACKAGE_ROOT / "legacy_v2_3.py")
    entry = read(ROOT / "apps" / "cvds_annotation_tool_v2_3.py")

    assert "C:\\Users\\shuai" not in legacy
    assert "anaconda3\\envs\\AI" not in legacy
    assert "AI_PYTHON" not in legacy
    assert "from cvds_annotation_tool.main import main" in entry
    assert "CVDS AI 辅助 YOLO 标注工具 v2.3" in legacy


def test_v23_ui_exposes_required_release_tools():
    legacy = read(PACKAGE_ROOT / "legacy_v2_3.py")
    diagnostics = read(PACKAGE_ROOT / "services" / "diagnostics.py")

    for text in ["环境自检", "数据集质检", "导出数据集", "打开回收站", "复制错误报告", "自动", "CPU", "GPU"]:
        assert text in legacy
    assert "move_dataset_item_to_trash" in legacy
    assert "atomic_write_text" in legacy
    assert "backup_existing_file" in legacy
    assert "batch_mode" in legacy
    assert "cancel_current_worker" in legacy
    assert "sam_available" in diagnostics
    assert "sam_error" in diagnostics


def test_v23_sam_is_disabled_when_runtime_does_not_export_sam():
    legacy = read(PACKAGE_ROOT / "legacy_v2_3.py")
    diagnostics = read(PACKAGE_ROOT / "services" / "diagnostics.py")

    assert "check_sam_available" in diagnostics
    assert "from ultralytics import SAM" in diagnostics
    assert "from ultralytics.models.sam import SAM" in diagnostics
    assert "当前发布包未包含 SAM 半自动分割环境" in legacy
    assert "diagnose.sam_available" in legacy
    assert "SamController(weights, device, parent=self)" in legacy
    assert legacy.index("diagnose.sam_available") < legacy.index("SamController(weights, device, parent=self)")


def test_v23_ai_release_keeps_base_release_and_uses_ai_name():
    packaging = ROOT / "apps" / "cvds_annotation_tool_v2_3" / "packaging"
    build_script = read(packaging / "build_release.ps1")
    spec = read(packaging / "cvds_annotation_tool.spec")
    ai_requirements = read(packaging / "requirements-ai.txt")

    assert "CVDS_Annotation_Tool_v2.3_AI" in build_script
    assert "CVDS_Annotation_Tool_v2.3" in build_script
    assert "$PackageName" in build_script
    assert "CVDS_ANNOTATION_PACKAGE_NAME" in spec
    assert "CVDS_ANNOTATION_INCLUDE_AI" in spec
    for package in ["ultralytics", "torch", "torchvision"]:
        assert package in ai_requirements
