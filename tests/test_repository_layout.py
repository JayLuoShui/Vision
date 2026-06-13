from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_does_not_contain_diagnostic_or_legacy_files() -> None:
    forbidden = [
        "README_LATENCY_TEST.md",
        "test_model_speed.py",
        "test_streaming_latency.py",
        "test_vllm_latency.py",
        "pt2openvino.py",
        "CVDS_Annotation_Tool.spec",
        "CVDS_Annotation_Tool_v2.spec",
        "CVDS_Jam_Video_Synthesizer.spec",
        "README_RELEASE.md",
    ]

    assert not [name for name in forbidden if (ROOT / name).exists()]


def test_project_files_are_grouped_by_responsibility() -> None:
    required = [
        "tools/diagnostics/llm_latency/README.md",
        "tools/diagnostics/llm_latency/test_model_speed.py",
        "tools/diagnostics/llm_latency/test_streaming_latency.py",
        "tools/diagnostics/llm_latency/test_vllm_latency.py",
        "apps/cvds_cpp_detector/README_RELEASE.md",
        "apps/cvds_cpp_detector/packaging/build_release.ps1",
        "apps/cvds_cpp_detector/docs/部署说明.md",
        "apps/cvds_annotation_tool_v2_3/packaging/build_release.ps1",
        "apps/cvds_annotation_tool_v2_3/docs/用户使用说明.md",
        "apps/cvds_jam_video_synthesizer/packaging/build_release.ps1",
        "apps/cvds_jam_video_synthesizer/docs/CVDS_Jam_Video_Synthesizer.md",
        "archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool.py",
        "archive/legacy_apps/cvds_annotation_tool/cvds_annotation_tool_v2.py",
        "archive/legacy_tests/cvds_annotation_tool/test_annotation_tool_v2.py",
        "archive/legacy_tests/cvds_annotation_tool/test_annotation_yolo_loading.py",
        "archive/legacy_packaging/CVDS_Annotation_Tool.spec",
        "archive/legacy_packaging/CVDS_Annotation_Tool_v2.spec",
        "archive/source_snapshots/cvds_annotation_tool_v2_3_legacy_flat",
    ]

    assert not [path for path in required if not (ROOT / path).exists()]


def test_active_tests_do_not_load_archived_annotation_tools() -> None:
    archived_tests = [
        ROOT / "tests" / "test_annotation_tool_v2.py",
        ROOT / "tests" / "test_annotation_yolo_loading.py",
    ]

    assert not [path for path in archived_tests if path.exists()]


def test_latency_tools_read_vllm_api_key_from_environment() -> None:
    tool_dir = ROOT / "tools" / "diagnostics" / "llm_latency"
    contents = "\n".join(
        path.read_text(encoding="utf-8")
        for path in tool_dir.glob("*")
        if path.is_file()
    )

    assert "VLLM_API_KEY" in contents
    assert '"Authorization": "Bearer ' not in contents
