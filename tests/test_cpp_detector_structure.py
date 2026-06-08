from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps" / "cvds_cpp_detector"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_cpp_detector_files_exist():
    expected = [
        APP_DIR / "CMakeLists.txt",
        APP_DIR / "README.md",
        APP_DIR / "src" / "main.cpp",
        APP_DIR / "src" / "MainWindow.h",
        APP_DIR / "src" / "MainWindow.cpp",
        APP_DIR / "src" / "RuntimePaths.h",
        APP_DIR / "src" / "RuntimePaths.cpp",
        APP_DIR / "configs" / "bytetrack.yaml",
        APP_DIR / "scripts" / "worker_entry.py",
        APP_DIR / "scripts" / "inspect_model_metadata.py",
        APP_DIR / "scripts" / "pt_video_flow_monitor.py",
    ]

    missing = [str(path) for path in expected if not path.exists()]

    assert missing == []


def test_cpp_ui_is_pt_video_flow_monitor_without_onnx_detection():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "视觉模型" in main_window
    assert "视频源" in main_window
    assert "流量监测" in main_window
    assert "绘制流量ROI" in main_window
    assert "模型训练" not in main_window
    assert "训练监控" not in main_window
    assert "ONNX模型" not in main_window
    assert "转换ONNX" not in main_window
    assert "ModelSourceMode" not in header
    assert "onnxEdit_" not in header
    assert "convertProcess_" not in header


def test_cpp_detection_runs_pt_python_worker_and_streams_metrics():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    header = read_text(APP_DIR / "src" / "MainWindow.h")

    assert "cvds_detector_worker.exe" in main_window
    assert "workerExePath" in main_window
    assert "QProcess process" in main_window
    assert "process.start(config_.workerPath, args)" in main_window
    assert '"--weights"' in main_window
    assert '"--source"' in main_window
    assert '"--roi"' in main_window
    assert '"--preview-path"' in main_window
    assert '"--tracker"' in main_window
    assert "flow_count" in main_window
    assert "inside_count" in main_window
    assert "pythonEdit_" not in header
    assert "pythonPath" not in header
    assert "defaultPythonPath" not in main_window
    assert "C:/Users/lenovo/miniconda3" not in main_window
    assert "Detector detector" not in main_window
    assert "export_pt_to_onnx.py" not in main_window


def test_cpp_runtime_paths_use_install_dir_and_appdata():
    header = read_text(APP_DIR / "src" / "RuntimePaths.h")
    source = read_text(APP_DIR / "src" / "RuntimePaths.cpp")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    for symbol in [
        "appDir",
        "runtimeDir",
        "workerExePath",
        "scriptsDir",
        "defaultWeightsDir",
        "defaultOutputDir",
        "writableAppDataDir",
        "trackerConfigPath",
    ]:
        assert symbol in header
        assert symbol in source

    assert "QStandardPaths::AppLocalDataLocation" in source
    assert "QCoreApplication::applicationDirPath()" in source
    assert "defaultOutputDir()" in main_window
    assert "findDefaultModelPath" in main_window
    assert "QDir::currentPath()" not in main_window


def test_cpp_has_environment_diagnose_and_three_device_modes():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "runEnvironmentDiagnose" in header
    assert "环境自检" in main_window
    assert '"diagnose"' in main_window
    assert "自动" in main_window
    assert "CPU" in main_window
    assert "GPU" in main_window
    assert 'currentData().toString()' in main_window
    assert 'addItem("自动", "auto")' in main_window
    assert 'addItem("CPU", "cpu")' in main_window
    assert 'addItem("GPU", "0")' in main_window


def test_cpp_start_detection_validates_packaged_runtime_resources():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "workerExePath()" in main_window
    assert "trackerConfigPath()" in main_window
    assert "isOutputDirWritable" in main_window
    assert "worker exe" in main_window.lower()
    assert "tracker yaml" in main_window.lower()
    assert "输出目录不可写" in main_window
    assert "error.left(2000)" not in main_window


def test_python_worker_entry_supports_required_subcommands():
    worker = read_text(APP_DIR / "scripts" / "worker_entry.py")

    assert 'subparsers.add_parser("detect"' in worker
    assert 'subparsers.add_parser("inspect-model"' in worker
    assert 'subparsers.add_parser("diagnose"' in worker
    assert "pt_video_flow_monitor" in worker
    assert "inspect_model_metadata" in worker
    assert "torch_available" in worker
    assert "cuda_available" in worker
    assert "recommend_device" in worker
    assert "当前运行包内 PyTorch 未启用 CUDA" in worker


def test_python_worker_diagnose_distinguishes_nvidia_driver_from_torch_cuda():
    worker = read_text(APP_DIR / "scripts" / "worker_entry.py")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "query_nvidia_smi" in worker
    assert "nvidia_driver_available" in worker
    assert "nvidia_driver_version" in worker
    assert "torch_cuda_version" in worker
    assert "cuda_issue" in worker
    assert "当前运行包内 PyTorch 未启用 CUDA" in worker
    assert "nvidia_driver_available" in main_window
    assert "torch_cuda_version" in main_window
    assert "cuda_issue" in main_window


def test_python_worker_falls_back_to_cpu_when_requested_gpu_is_unavailable():
    worker = read_text(APP_DIR / "scripts" / "worker_entry.py")
    monitor = read_text(APP_DIR / "scripts" / "pt_video_flow_monitor.py")

    assert "已自动切换 CPU" in worker
    assert "raise RuntimeError(gpu_unavailable_message())" not in worker
    assert "return \"cpu\"" in worker.split("def normalize_detect_device")[1]
    assert "return \"cpu\"" in monitor.split("def validate_device")[1]
    assert "当前运行环境未启用 CUDA，已自动切换 CPU 推理。" in monitor


def test_release_worker_requirements_use_cuda_torch_wheels():
    requirements = read_text(ROOT / "packaging" / "requirements-worker.txt")

    assert "https://download.pytorch.org/whl/cu128" in requirements
    assert "torch==2.11.0+cu128" in requirements
    assert "torchvision==0.26.0+cu128" in requirements


def test_release_packaging_files_exist_and_define_installer():
    expected = [
        ROOT / "packaging" / "build_release.ps1",
        ROOT / "packaging" / "make_installer.iss",
        ROOT / "packaging" / "requirements-worker.txt",
        ROOT / "packaging" / "README_RELEASE.md",
        ROOT / "README_RELEASE.md",
        ROOT / "VERSION.txt",
        ROOT / "docs" / "用户使用说明.md",
        ROOT / "docs" / "部署说明.md",
        ROOT / "docs" / "故障排查.md",
    ]
    missing = [str(path) for path in expected if not path.exists()]

    assert missing == []

    build_script = read_text(ROOT / "packaging" / "build_release.ps1")
    installer = read_text(ROOT / "packaging" / "make_installer.iss")
    requirements = read_text(ROOT / "packaging" / "requirements-worker.txt")

    assert "windeployqt" in build_script
    assert "PyInstaller" in build_script
    assert "cvds_detector_worker.exe diagnose" in build_script
    assert "--collect-all nvidia" in build_script
    assert "CVDS_Package_Flow_Detector" in build_script
    assert "{autopf}\\CVDS\\CVDS包裹流量检测工具" in installer
    assert "cvds_detector_worker.exe" in installer
    assert "ultralytics" in requirements
    assert "torch" in requirements
    assert "opencv-python" in requirements


def test_release_files_do_not_contain_developer_absolute_paths():
    paths = [
        APP_DIR / "src" / "MainWindow.cpp",
        APP_DIR / "src" / "MainWindow.h",
        APP_DIR / "src" / "RuntimePaths.cpp",
        APP_DIR / "CMakeLists.txt",
        ROOT / "README_RELEASE.md",
        ROOT / "packaging" / "README_RELEASE.md",
        ROOT / "docs" / "部署说明.md",
    ]
    forbidden = [
        "C:/Users/lenovo",
        "C:\\Users\\lenovo",
        "C:/Qt",
        "C:/tools/opencv",
        "miniconda3",
        "conda yolo26",
    ]

    for path in paths:
        text = read_text(path)
        for value in forbidden:
            assert value not in text, f"{value} found in {path}"


def test_cpp_preview_label_supports_polygon_roi_and_undo():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "QVector<QPoint>" in header
    assert "undoCurrentPoint" in header
    assert "finishCurrentPolygon" in header
    assert "keyPressEvent" in header
    assert "activeRoiClosed" in header
    assert "flowRoiClosed_" in header
    assert "detectRoiClosed_" in header
    assert "polygonToText" in header
    assert "drawPolygon" in main_window
    assert "撤回ROI点" in main_window
    assert "右键完成" in main_window
    assert "完成多边形" not in main_window
    assert "rectToPolygonText" not in header
    assert "QRect flowRoi_" not in header


def test_cpp_roi_polygon_finishes_with_right_click_or_enter_only():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "event->button() == Qt::RightButton" in main_window
    assert "finishCurrentPolygon();" in main_window.split("event->button() == Qt::RightButton")[1]
    assert "event->key() == Qt::Key_Return" in main_window
    assert "event->key() == Qt::Key_Enter" in main_window
    assert "mouseDoubleClickEvent" not in main_window
    assert "右键完成" in main_window
    assert "activeRoiClosed() = false" in main_window
    assert "polygonToText(activePolygon(), activeRoiClosed())" in main_window


def test_cpp_left_panel_uses_scroll_area_for_maximized_layout():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "#include <QScrollArea>" in main_window
    assert "QScrollArea" in main_window
    assert "setWidgetResizable(true)" in main_window
    assert "setMinimumWidth(520)" in main_window
    assert "setMaximumWidth(680)" in main_window


def test_cpp_industrial_theme_and_spin_step_buttons_are_visible():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "#101820" in main_window
    assert "#1f2a2e" in main_window
    assert "#d49a20" in main_window
    assert "#1f6f50" in main_window
    assert "#8f1d1d" in main_window
    assert "QSpinBox::up-button" in main_window
    assert "QDoubleSpinBox::up-button" in main_window
    assert "QSpinBox::down-button" in main_window
    assert "QDoubleSpinBox::down-button" in main_window
    assert "QSpinBox::up-arrow" in main_window
    assert "QSpinBox::down-arrow" in main_window
    assert "QComboBox::down-arrow" in main_window
    assert "border-bottom:7px solid #d49a20" in main_window
    assert "border-top:7px solid #d49a20" in main_window


def test_cpp_remembers_paths_and_supports_hikvision_stream():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "loadSettings" in header
    assert "saveSettings" in header
    assert "QSettings" in main_window
    assert "lastModelPath" in main_window
    assert "lastSourcePath" in main_window
    assert "applyHikvisionStream" in header
    assert "buildHikvisionRtsp" in header
    assert "海康相机" in main_window
    assert "rtsp" in main_window
    assert "Streaming/Channels" in main_window
    assert "hikIpEdit_" in header
    assert "hikChannelSpin_" in header


def test_cpp_application_name_is_package_flow_detector():
    main_cpp = read_text(APP_DIR / "src" / "main.cpp")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "CVDS包裹流量检测工具" in main_cpp
    assert "CVDS包裹流量检测工具" in main_window


def test_cpp_jam_controls_and_signal_handling_exist():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "jamSecondsSpin_" in header
    assert "jamSignalPath" in header
    assert '"--jam-seconds"' in main_window
    assert '"--jam-signal-path"' in main_window
    assert 'type == "jam"' in main_window
    assert "堵包" in main_window
    assert "jam_signals.jsonl" in main_window


def test_pt_video_flow_monitor_uses_ultralytics_tracking_and_roi_counting():
    monitor = read_text(APP_DIR / "scripts" / "pt_video_flow_monitor.py")

    assert "from ultralytics import YOLO" in monitor
    assert "model.track" in monitor
    assert "--weights" in monitor
    assert "--source" in monitor
    assert "--roi" in monitor
    assert "--detect-roi" in monitor
    assert "--preview-path" in monitor
    assert "flow_count" in monitor
    assert "inside_count" in monitor
    assert "cv2.polylines" in monitor
    assert "json.dumps" in monitor


def test_pt_video_flow_monitor_detects_jam_and_writes_signal():
    monitor = read_text(APP_DIR / "scripts" / "pt_video_flow_monitor.py")

    assert "--jam-seconds" in monitor
    assert "--jam-signal-path" in monitor
    assert "jam_active" in monitor
    assert "last_flow_change_frame" in monitor
    assert '"type": "jam"' in monitor
    assert "jam_signals" in monitor
    assert "write_jsonl" in monitor


def test_pt_video_flow_monitor_does_not_count_unprocessed_max_frame():
    monitor = read_text(APP_DIR / "scripts" / "pt_video_flow_monitor.py")

    assert "if args.max_frames > 0 and frame_idx >= args.max_frames:" in monitor
    assert monitor.index("if args.max_frames > 0 and frame_idx >= args.max_frames:") < monitor.index("frame_idx += 1")


def test_cmake_no_longer_links_onnx_runtime_for_detection():
    cmake = read_text(APP_DIR / "CMakeLists.txt")

    assert "ONNXRUNTIME_ROOT" not in cmake
    assert "onnxruntime" not in cmake.lower()
    assert "Detector.cpp" not in cmake
    assert "pt_video_flow_monitor.py" in cmake
    assert "Qt6::Widgets" in cmake
    assert "OpenCV" in cmake


def test_cpp_class_labels_are_loaded_from_pt_metadata():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    inspector = read_text(APP_DIR / "scripts" / "inspect_model_metadata.py")

    assert "classCombo_" in header
    assert "loadedLabels_" in header
    assert "refreshModelMetadata" in header
    assert "全部类别" in main_window
    assert "refreshModelMetadata" in main_window
    assert "YOLO" in inspector
    assert 'labels.push_back("parcel")' not in main_window


def test_cpp_startup_defers_heavy_model_and_video_loading():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    constructor_body = main_window.split("MainWindow::MainWindow(QWidget* parent)")[1].split("MainWindow::~MainWindow()")[0]
    start_detection_body = main_window.split("void MainWindow::startDetection()")[1].split("void MainWindow::stopDetection()")[0]

    assert "refreshModelMetadata();" not in constructor_body
    assert "loadVideoPreviewFrame();" not in constructor_body
    assert "refreshModelMetadata();" in start_detection_body
    assert "延迟加载模型类别和视频预览" in constructor_body


def test_cpp_left_sidebar_wheel_does_not_change_parameter_controls():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "class ScrollSafeSpinBox" in main_window
    assert "class ScrollSafeDoubleSpinBox" in main_window
    assert "class ScrollSafeComboBox" in main_window
    assert "void wheelEvent(QWheelEvent* event) override" in main_window
    assert "event->ignore();" in main_window
    assert "new ScrollSafeSpinBox" in main_window
    assert "new ScrollSafeDoubleSpinBox" in main_window
    assert "new ScrollSafeComboBox" in main_window


def test_cpp_left_sidebar_scrollbar_has_smoother_motion():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "#include <QScrollBar>" in main_window
    assert "verticalScrollBar()->setSingleStep(28)" in main_window
    assert "verticalScrollBar()->setPageStep(160)" in main_window
    assert "QScrollBar::handle:vertical" in main_window


if __name__ == "__main__":
    test_cpp_detector_files_exist()
    test_cpp_ui_is_pt_video_flow_monitor_without_onnx_detection()
    test_cpp_detection_runs_pt_python_worker_and_streams_metrics()
    test_cpp_runtime_paths_use_install_dir_and_appdata()
    test_cpp_has_environment_diagnose_and_three_device_modes()
    test_cpp_start_detection_validates_packaged_runtime_resources()
    test_python_worker_entry_supports_required_subcommands()
    test_python_worker_diagnose_distinguishes_nvidia_driver_from_torch_cuda()
    test_python_worker_falls_back_to_cpu_when_requested_gpu_is_unavailable()
    test_release_worker_requirements_use_cuda_torch_wheels()
    test_release_packaging_files_exist_and_define_installer()
    test_release_files_do_not_contain_developer_absolute_paths()
    test_cpp_preview_label_supports_polygon_roi_and_undo()
    test_cpp_roi_polygon_finishes_with_right_click_or_enter_only()
    test_cpp_left_panel_uses_scroll_area_for_maximized_layout()
    test_cpp_industrial_theme_and_spin_step_buttons_are_visible()
    test_cpp_remembers_paths_and_supports_hikvision_stream()
    test_cpp_application_name_is_package_flow_detector()
    test_cpp_jam_controls_and_signal_handling_exist()
    test_pt_video_flow_monitor_uses_ultralytics_tracking_and_roi_counting()
    test_pt_video_flow_monitor_detects_jam_and_writes_signal()
    test_pt_video_flow_monitor_does_not_count_unprocessed_max_frame()
    test_cmake_no_longer_links_onnx_runtime_for_detection()
    test_cpp_class_labels_are_loaded_from_pt_metadata()
    test_cpp_startup_defers_heavy_model_and_video_loading()
    test_cpp_left_sidebar_wheel_does_not_change_parameter_controls()
    test_cpp_left_sidebar_scrollbar_has_smoother_motion()
    print("27 passed")
