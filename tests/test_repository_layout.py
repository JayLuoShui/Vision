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


def test_dws_service_and_pretrained_weights_use_grouped_locations() -> None:
    required = [
        "apps/DWSVisionCountService/app/main.py",
        "apps/DWSVisionCountService/docs/WINDOWS_USER_GUIDE.md",
    ]
    obsolete = [
        "DWSVisionCountService",
        "yolo26n.pt",
        "yolo26s.pt",
        "yolo26s-seg.pt",
    ]

    assert not [path for path in required if not (ROOT / path).exists()]
    assert not [path for path in obsolete if (ROOT / path).exists()]


def test_scoped_markdown_files_are_not_kept_at_repository_root() -> None:
    required = [
        "apps/cvds_annotation_tool_v2_3/CHANGELOG.md",
        ".opencode/docs/OPENCODE_TUNING.md",
    ]
    obsolete = [
        "CHANGELOG.md",
        "OPENCODE_TUNING.md",
    ]

    assert not [path for path in required if not (ROOT / path).exists()]
    assert not [path for path in obsolete if (ROOT / path).exists()]


def test_training_defaults_use_pretrained_weight_directory() -> None:
    expected_references = {
        "scripts/train_yolo26n_package.py": 'ROOT / "weights" / "pretrained" / "yolo26n.pt"',
        "scripts/train_yolo26s_manual_annotation.py": 'ROOT / "weights" / "pretrained" / "yolo26s.pt"',
        "scripts/train_yolomask_yolo26seg.py": "weights/pretrained/yolo26s-seg.pt",
        "apps/cvds_qt_app.py": 'ROOT / "weights" / "pretrained" / "yolo26n.pt"',
    }

    missing = [
        path
        for path, expected in expected_references.items()
        if expected not in (ROOT / path).read_text(encoding="utf-8")
    ]

    assert not missing


def test_opencode_watcher_ignores_high_churn_non_source_directories() -> None:
    config_text = (ROOT / "opencode.json").read_text(encoding="utf-8")
    required_patterns = [
        "audit/**",
        "archive/**",
        ".superpowers/**",
        "tools/downloads/**",
        "apps/DWSVisionCountService/cache/**",
        "apps/DWSVisionCountService/debug/**",
    ]

    missing = [pattern for pattern in required_patterns if pattern not in config_text]

    assert not missing
