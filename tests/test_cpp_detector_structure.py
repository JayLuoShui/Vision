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
        APP_DIR / "src" / "RegionConfig.h",
        APP_DIR / "src" / "RegionConfig.cpp",
        APP_DIR / "src" / "RuntimePaths.h",
        APP_DIR / "src" / "RuntimePaths.cpp",
        APP_DIR / "src" / "resources.qrc",
        APP_DIR / "src" / "app_icon.rc",
        APP_DIR / "assets" / "cogy_brand.png",
        APP_DIR / "assets" / "cogy_mark.png",
        APP_DIR / "assets" / "cogy_app.ico",
        APP_DIR / "configs" / "bytetrack.yaml",
        APP_DIR / "configs" / "regions.example.json",
        APP_DIR / "scripts" / "worker_entry.py",
        APP_DIR / "scripts" / "inspect_model_metadata.py",
        APP_DIR / "scripts" / "pt_video_flow_monitor.py",
    ]

    missing = [str(path) for path in expected if not path.exists()]

    assert missing == []


def test_cpp_ui_uses_unified_model_selector_inside_inference_panel():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    path_panel = main_window.split("QWidget* MainWindow::buildPathPanel()")[1].split(
        "QWidget* MainWindow::buildParamPanel()"
    )[0]
    param_panel = main_window.split("QWidget* MainWindow::buildParamPanel()")[1].split(
        "QWidget* MainWindow::buildRoiPanel()"
    )[0]

    assert "视频源" in main_window
    assert "流量监测" in main_window
    assert "绘制流量ROI" in main_window
    assert "模型训练" not in main_window
    assert "训练监控" not in main_window
    assert "转换ONNX" not in main_window
    assert "ModelSourceMode" not in header
    assert "onnxEdit_" not in header
    assert "convertProcess_" not in header
    assert "视觉模型" not in path_panel
    assert "模型格式" not in path_panel
    assert "视觉模型" in param_panel
    assert 'form->addRow("选择方式", modelButtons)' in param_panel
    assert "modelEdit_" in header
    assert "ptEdit_" not in header


def test_cpp_detection_runs_unified_python_worker_and_streams_metrics():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    header = read_text(APP_DIR / "src" / "MainWindow.h")

    assert "cvds_detector_worker.exe" in main_window
    assert "workerExePath" in main_window
    assert "QProcess process" in main_window
    assert "process.start(config_.workerPath, args)" in main_window
    assert '"--model"' in main_window
    assert '"--weights"' not in main_window
    assert '"--source"' in main_window
    assert '"--rtsp-transport"' in main_window
    assert '"--regions"' in main_window
    assert "regions.json" in main_window
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
        "configDir",
        "defaultRegionsConfigPath",
        "regionsExamplePath",
        "trackerConfigPath",
    ]:
        assert symbol in header
        assert symbol in source

    assert "QStandardPaths::AppLocalDataLocation" in source
    assert "QCoreApplication::applicationDirPath()" in source
    assert "defaultOutputDir()" in main_window
    assert "findDefaultModelPath" in main_window
    assert "QDir::currentPath()" not in main_window


def test_cpp_has_environment_diagnose_and_backend_aware_device_modes():
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
    assert 'addItem("NVIDIA GPU", "0")' in main_window
    assert 'addItem("Intel GPU", "intel:gpu")' in main_window
    assert 'addItem("Intel NPU", "intel:npu")' in main_window


def test_cpp_start_detection_validates_packaged_runtime_resources():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "workerExePath()" in main_window
    assert "trackerConfigPath()" in main_window
    assert "isOutputDirWritable" in main_window
    assert "worker exe" in main_window.lower()
    assert "tracker yaml" in main_window.lower()
    assert "输出目录不可写" in main_window
    assert "error.left(2000)" not in main_window


def test_cpp_model_metadata_loading_is_async_and_blocks_detection_on_failure():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "beginModelMetadataRefresh" in header
    assert "finishModelMetadataRefresh" in header
    assert "modelInspectProcess_" in header
    assert "startDetectionAfterModelInspect_" in header
    assert "QTimer::singleShot(30000" in main_window
    assert "waitForStarted(5000)" not in main_window.split("void MainWindow::refreshModelMetadata()")[1].split(
        "void MainWindow::runEnvironmentDiagnose()"
    )[0]
    assert "waitForFinished(30000)" not in main_window.split("void MainWindow::refreshModelMetadata()")[1].split(
        "void MainWindow::runEnvironmentDiagnose()"
    )[0]
    start_body = main_window.split("void MainWindow::startDetection()")[1].split("void MainWindow::stopDetection()")[0]
    assert "beginModelMetadataRefresh(true)" in start_body
    assert "loadedModelPath_" in start_body


def test_python_worker_entry_supports_required_subcommands():
    worker = read_text(APP_DIR / "scripts" / "worker_entry.py")

    assert 'subparsers.add_parser("detect"' in worker
    assert 'subparsers.add_parser("inspect-model"' in worker
    assert 'subparsers.add_parser("diagnose"' in worker
    assert "pt_video_flow_monitor" in worker
    assert "inspect_model_metadata" in worker
    assert "torch_available" in worker
    assert "cuda_available" in worker
    assert "onnx_available" in worker
    assert "onnxruntime_available" in worker
    assert "openvino_available" in worker
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
    assert 'object.value("onnxruntime_available")' in main_window
    assert 'object.value("openvino_available")' in main_window


def test_python_worker_rejects_unavailable_explicit_devices():
    worker = read_text(APP_DIR / "scripts" / "worker_entry.py")
    monitor = read_text(APP_DIR / "scripts" / "pt_video_flow_monitor.py")

    assert "已自动切换 CPU" not in worker
    assert "raise RuntimeError(gpu_unavailable_message())" in worker
    assert "OpenVINO 设备不可用" in worker
    assert "OpenVINO 设备不可用" in monitor


def test_release_worker_requirements_use_cuda_torch_wheels():
    requirements = read_text(APP_DIR / "packaging" / "requirements-worker.txt")

    assert "https://download.pytorch.org/whl/cu128" in requirements
    assert "torch==2.11.0+cu128" in requirements
    assert "torchvision==0.26.0+cu128" in requirements


def test_release_worker_packages_onnx_and_openvino_backends():
    requirements = read_text(APP_DIR / "packaging" / "requirements-worker.txt")
    build_script = read_text(APP_DIR / "packaging" / "build_release.ps1")
    cmake = read_text(APP_DIR / "CMakeLists.txt")

    assert "onnxruntime-gpu" in requirements
    assert "openvino" in requirements
    assert "lap>=0.5.12" in requirements
    assert '"onnxruntime"' in build_script
    assert '"openvino"' in build_script
    assert '-Filter "*.onnx"' in build_script
    assert '-Filter "*_openvino_model"' in build_script
    assert 'PATTERN "*.onnx"' in cmake
    assert 'PATTERN "*.xml"' in cmake
    assert 'PATTERN "*.bin"' in cmake
    assert 'PATTERN "*_openvino_model"' in cmake


def test_release_branding_uses_online_parcel_flow_monitor_name():
    installer = read_text(APP_DIR / "packaging" / "make_installer.iss")
    readme = read_text(APP_DIR / "README.md")

    assert "CVDS在线包裹流量监测" in installer
    assert "CVDS包裹流量检测工具" not in installer
    assert "PT、ONNX、OpenVINO" in readme
    assert "本地文件" in readme
    assert "视频流" in readme


def test_release_packaging_files_exist_and_define_installer():
    expected = [
        APP_DIR / "packaging" / "build_release.ps1",
        APP_DIR / "packaging" / "make_installer.iss",
        APP_DIR / "packaging" / "requirements-worker.txt",
        APP_DIR / "packaging" / "README_RELEASE.md",
        APP_DIR / "README_RELEASE.md",
        ROOT / "VERSION.txt",
        APP_DIR / "docs" / "部署说明.md",
    ]
    missing = [str(path) for path in expected if not path.exists()]

    assert missing == []

    build_script = read_text(APP_DIR / "packaging" / "build_release.ps1")
    installer = read_text(APP_DIR / "packaging" / "make_installer.iss")
    requirements = read_text(APP_DIR / "packaging" / "requirements-worker.txt")

    assert "windeployqt" in build_script
    assert "PyInstaller" in build_script
    assert "cvds_detector_worker.exe diagnose" in build_script
    assert '"--collect-all"\n    "ultralytics"' in build_script
    assert '"--collect-all"\n    "cv2"' in build_script
    for oversized_package in ["torch", "torchvision", "nvidia"]:
        assert f'"--collect-all"\n    "{oversized_package}"' not in build_script
    assert "CVDS_Package_Flow_Detector" in build_script
    assert '"configs\\regions.example.json"' in build_script
    assert "{autopf}\\CVDS\\CVDS在线包裹流量监测" in installer
    assert "cvds_detector_worker.exe" in installer
    assert "ultralytics" in requirements
    assert "torch" in requirements
    assert "opencv-python" in requirements
    assert "pillow" in requirements.lower()


def test_cmake_installs_detector_specific_docs():
    cmake = read_text(APP_DIR / "CMakeLists.txt")

    assert 'install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/docs"' in cmake
    assert '"${PROJECT_ROOT}/docs"' not in cmake
    assert 'PATTERN "__pycache__" EXCLUDE' in cmake


def test_release_files_do_not_contain_developer_absolute_paths():
    paths = [
        APP_DIR / "src" / "MainWindow.cpp",
        APP_DIR / "src" / "MainWindow.h",
        APP_DIR / "src" / "RuntimePaths.cpp",
        APP_DIR / "CMakeLists.txt",
        APP_DIR / "README_RELEASE.md",
        APP_DIR / "packaging" / "README_RELEASE.md",
        APP_DIR / "docs" / "部署说明.md",
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


def test_cpp_monitor_layout_prioritizes_preview_and_keeps_left_panel_compact():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    main = read_text(APP_DIR / "src" / "main.cpp")

    assert "#include <QScrollArea>" in main_window
    assert "#include <QSplitter>" in main_window
    assert "setMinimumSize(320, 180)" not in main_window
    assert "setMinimumSize(160, 90)" in main_window
    assert "QScrollArea" in main_window
    assert "setWidgetResizable(true)" in main_window
    assert "setMinimumSize(800, 420)" in main_window
    assert "resize(800, 420)" in main_window
    assert "resize(1480, 940)" not in main_window
    assert "brandBar->setFixedHeight(42)" in main_window
    assert "leftShell->setMinimumWidth(210)" in main_window
    assert "leftShell->setMaximumWidth(340)" in main_window
    assert "mainSplitter_->width() * 24 / 100" in main_window
    assert "qBound(210, mainSplitter_->width() * 24 / 100, 340)" in main_window
    assert "void MainWindow::resizeEvent(QResizeEvent* event)" in main_window
    assert "resizeSidebarToStitchRatio();" in main_window
    assert "mainSplitter_" in header
    assert "settingsPanel_" in header
    assert "qBound(11, leftWidth / 26, 14)" in main_window
    assert "&QSplitter::splitterMoved" in main_window
    assert "right->setMinimumWidth(0)" in main_window
    assert "right->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding)" in main_window
    assert "rightLayout->setSizeConstraint(QLayout::SetNoConstraint)" in main_window
    assert "previewLabel_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding)" in main_window
    assert "splitter->setStretchFactor(1, 1)" in main_window
    assert "window.showMaximized()" in main


def test_cpp_video_stream_application_starts_live_preview_before_detection():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    apply_stream = main_window.split("void MainWindow::applyHikvisionStream()")[1].split(
        "void MainWindow::testVideoStream()"
    )[0]
    start_detection = main_window.split("void MainWindow::startDetection()")[1].split(
        "void MainWindow::stopDetection()"
    )[0]

    assert "class VideoPreviewWorker" in header
    assert "startVideoPreview" in header
    assert "stopVideoPreview" in header
    assert "previewThread_" in header
    assert "previewWorker_" in header
    assert "pendingPreviewSource_" in header
    assert "startDetectionAfterPreviewStops_" in header
    assert "startVideoPreview();" in apply_stream
    assert "stopVideoPreview();" in start_detection
    browse_source = main_window.split("void MainWindow::browseSource()")[1].split(
        "void MainWindow::applyHikvisionStream()"
    )[0]
    assert "stopVideoPreview();" in browse_source
    stop_preview = main_window.split("void MainWindow::stopVideoPreview()")[1].split(
        "void MainWindow::refreshRuntimeOverview()"
    )[0]
    assert "thread->wait();" not in stop_preview
    assert "pendingPreviewSource_" in main_window
    assert "QTimer::singleShot(0, this, &MainWindow::startDetection)" in main_window
    assert "实时视频流将在开始检测后显示" not in main_window
    assert "VideoPreviewWorker::frameReady" in main_window
    assert "previewLabel_->setImage" in main_window


def test_cpp_channel_switch_never_waits_for_rtsp_thread_on_ui_thread():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    start_preview = main_window.split("void MainWindow::startVideoPreview()")[1].split(
        "void MainWindow::stopVideoPreview()"
    )[0]
    stop_preview = main_window.split("void MainWindow::stopVideoPreview()")[1].split(
        "void MainWindow::refreshRuntimeOverview()"
    )[0]

    assert "previewFrameAccepted_ = false;" in stop_preview
    assert "QMetaObject::invokeMethod(worker, \"stop\", Qt::DirectConnection);" in stop_preview
    assert "wait(" not in stop_preview
    assert "wait()" not in stop_preview
    assert "if (previewThread_ != nullptr)" in start_preview
    assert "pendingPreviewSource_" in start_preview
    assert "launchPendingVideoPreview" in main_window


def test_cpp_roi_is_session_only_and_cleared_on_every_startup():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    constructor = main_window.split("MainWindow::MainWindow(QWidget* parent)")[1].split(
        "MainWindow::~MainWindow()"
    )[0]
    load_settings = main_window.split("void MainWindow::loadSettings()")[1].split(
        "void MainWindow::saveSettings() const"
    )[0]
    save_settings = main_window.split("void MainWindow::saveSettings() const")[1].split(
        "void MainWindow::populateClassCombo"
    )[0]

    assert "QFileInfo::exists(RuntimePaths::defaultRegionsConfigPath())" not in constructor
    assert "ensureDefaultRegion();" in constructor
    assert "detectRoiEdit_->clear();" in constructor
    assert 'settings.remove("lastDetectRoi")' in load_settings
    assert 'settings.value("lastDetectRoi"' not in load_settings
    assert 'settings.setValue("lastDetectRoi"' not in save_settings


def test_cpp_control_panel_can_collapse_and_auto_collapses_when_detection_starts():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    start_detection = main_window.split("void MainWindow::startDetection()")[1].split(
        "void MainWindow::stopDetection()"
    )[0]

    assert "settingsToggleButton_" in header
    assert "setSettingsPanelCollapsed" in header
    assert 'new QPushButton("收起控制面板"' in main_window
    assert 'collapsed ? "展开控制面板" : "收起控制面板"' in main_window
    assert "settingsPanel_->setVisible(!collapsed)" in main_window
    assert "setSettingsPanelCollapsed(true);" in start_detection


def test_cpp_dashboard_is_responsive_and_region_details_are_collapsible():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    dashboard = main_window.split("QWidget* MainWindow::buildDashboardPanel()")[1].split(
        "QString MainWindow::buildHikvisionRtsp()"
    )[0]
    assert "logToggleButton_" in header
    assert "regionDetailsToggleButton_" in header
    assert "regionDetailsContent_" in header
    assert 'new QPushButton("展开运行日志"' in main_window
    assert 'new QPushButton("展开区域统计"' in main_window
    assert "logEdit_->setVisible(false)" in main_window
    assert "regionDetailsContent_->setVisible(false)" in main_window
    assert "logToggleButton_->setCheckable(true)" in main_window
    assert "regionDetailsToggleButton_->setCheckable(true)" in main_window
    assert 'checked ? "收起运行日志" : "展开运行日志"' in main_window
    assert 'checked ? "收起区域统计" : "展开区域统计"' in main_window
    assert "regionPanel->setMinimumHeight(28)" in main_window
    assert "regionPanel->setMaximumHeight(28)" in main_window
    assert "regionTable_->setMinimumHeight(132)" in main_window
    assert "regionTable_->setMaximumHeight(64)" not in main_window
    assert "regionTable_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding)" in main_window
    assert "regionPanel->setFixedHeight(80)" not in main_window
    assert "regionEmptyLabel_" in header
    assert "尚未配置监测区域" in main_window
    assert "card->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed)" in dashboard
    assert "cardLayout->setSizeConstraint(QLayout::SetNoConstraint)" in dashboard
    assert "titleLabel->setSizePolicy(QSizePolicy::Minimum, QSizePolicy::Preferred)" in dashboard
    assert "new QHBoxLayout(box)" in dashboard
    assert "layout->setSizeConstraint(QLayout::SetNoConstraint)" in dashboard
    assert "font-size:18px" in main_window
    assert "compactDashboard" not in dashboard
    assert "availableGeometry().width()" not in dashboard
    assert "card->setFixedWidth" not in dashboard
    assert "box->setFixedHeight(56)" in dashboard
    assert 'layout->addWidget(buildCard("累计包裹", &kpiTotalCountValueLabel_), 1)' in dashboard
    assert 'layout->addWidget(buildCard("当前状态", &kpiStatusValueLabel_), 1)' in dashboard
    assert 'layout->addWidget(buildCard("区域内包裹", &kpiInsideCountValueLabel_), 1)' in dashboard
    assert 'layout->addWidget(buildCard("堵包次数", &kpiJamCountValueLabel_), 1)' in dashboard


def test_cpp_start_detection_refreshes_status_after_worker_thread_is_created():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    start_detection = main_window.split("void MainWindow::startDetection()")[1].split(
        "void MainWindow::stopDetection()"
    )[0]

    worker_created = start_detection.index("workerThread_ = new QThread(this);")
    assert start_detection.find("refreshRegionTable();", worker_created) > worker_created


def test_cpp_stitch_a_sidebar_uses_collapsible_navigation():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "buildSidebarNavigationButton" in header
    assert "setSidebarPanelVisible" in header
    assert '"视频源"' in main_window
    assert '"推理参数"' in main_window
    assert "ROI 区域" in main_window
    assert "检测控制" in main_window
    assert "buildControlPanel" in header
    assert "controlPanel_" in header
    action_panel = main_window.split("QWidget* MainWindow::buildActionPanel()")[1].split(
        "QWidget* MainWindow::buildControlPanel()"
    )[0]
    control_panel = main_window.split("QWidget* MainWindow::buildControlPanel()")[1].split(
        "QPushButton* MainWindow::buildSidebarNavigationButton"
    )[0]
    assert "diagnoseButton_" not in action_panel
    assert "diagnoseButton_" in control_panel
    assert 'setObjectName("sidebarNavigation")' in main_window
    assert 'setObjectName("sidebarNavigationButton")' in main_window
    assert "pathPanel_->setVisible(false)" in main_window
    assert "videoSourceButton->setChecked(true);\n    pathPanel_->setVisible(true);" in main_window
    assert "paramPanel_->setVisible(false)" in main_window
    assert "roiPanel_->setVisible(false)" in main_window


def test_cpp_path_fields_hide_full_paths_except_after_selection():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert 'setProperty("fullPath"' in main_window
    assert 'property("fullPath")' in main_window
    assert "privatePathLabel" in main_window
    assert "setPrivatePath" in main_window
    assert "QTimer::singleShot(5000" in main_window
    assert "modelEdit_->setReadOnly(true)" in main_window
    assert "sourceEdit_->setReadOnly(true)" in main_window
    assert "outputEdit_->setReadOnly(true)" in main_window
    assert "setPrivatePath(modelEdit_, path, true)" in main_window
    assert "setPrivatePath(sourceEdit_, path, true)" in main_window
    assert "setPrivatePath(outputEdit_, path, true)" in main_window
    assert "modelEdit_->text().trimmed()" not in main_window
    assert "sourceEdit_->text().trimmed()" not in main_window
    assert "outputEdit_->text().trimmed()" not in main_window
    private_label = main_window.split("QString privatePathLabel(const QString& path)")[1].split(
        "void setPrivatePath"
    )[0]
    assert 'trimmed.contains("://")' in private_label
    assert private_label.index('trimmed.contains("://")') < private_label.index("const QUrl url")


def test_cpp_region_table_only_displays_seconds_during_active_jam():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "state.jamActive ? state.staleSeconds : 0.0" in main_window


def test_cpp_cogy_stitch_theme_and_spin_step_buttons_are_visible():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    for color in [
        "#0B1118",
        "#111B25",
        "#172431",
        "#263746",
        "#2F88F5",
        "#4DA3FF",
        "#F3F7FA",
        "#8FA5B8",
        "#36C98F",
        "#FFB84D",
        "#F25555",
    ]:
        assert color in main_window
    assert "QSpinBox::up-button" in main_window
    assert "QDoubleSpinBox::up-button" in main_window
    assert "QSpinBox::down-button" in main_window
    assert "QDoubleSpinBox::down-button" in main_window
    assert "QSpinBox::up-arrow" in main_window
    assert "QSpinBox::down-arrow" in main_window
    assert "QComboBox::down-arrow" in main_window
    assert "border-bottom:7px solid #4DA3FF" in main_window
    assert "border-top:7px solid #4DA3FF" in main_window


def test_cpp_cogy_brand_bar_and_application_icons_are_embedded():
    cmake = read_text(APP_DIR / "CMakeLists.txt")
    main_cpp = read_text(APP_DIR / "src" / "main.cpp")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    resources = read_text(APP_DIR / "src" / "resources.qrc")
    app_icon = read_text(APP_DIR / "src" / "app_icon.rc")
    installer = read_text(APP_DIR / "packaging" / "make_installer.iss")

    assert "src/resources.qrc" in cmake
    assert "src/app_icon.rc" in cmake
    assert 'prefix="/branding"' in resources
    assert 'alias="cogy_brand.png"' in resources
    assert 'alias="cogy_mark.png"' in resources
    assert "cogy_app.ico" in app_icon
    assert 'QIcon(":/branding/cogy_mark.png")' in main_cpp
    assert 'setObjectName("brandBar")' in main_window
    assert 'setObjectName("brandLogo")' in main_window
    assert 'setObjectName("systemStatus")' in main_window
    assert "CVDS ONLINE PARCEL FLOW MONITOR" in main_window
    assert "在线包裹流量监测" in main_window
    assert "CVDS C++ DETECTOR" not in main_window
    assert "系统就绪" in main_window
    assert "SetupIconFile" in installer
    assert "cogy_app.ico" in installer


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
    assert "testVideoStream" in header
    assert "本地文件" in main_window
    assert "视频流" in main_window
    assert "海康设备" in main_window
    assert "rtsp" in main_window
    assert "Streaming/Channels" in main_window
    assert "hikIpEdit_" in header
    assert "hikChannelSpin_" in header
    assert "hikRtspPortSpin_" in header
    assert "hikStreamCombo_" in header
    assert "hikTransportCombo_" in header
    assert "主码流" in main_window
    assert "子码流" in main_window
    assert 'addItem("TCP", "tcp")' in main_window
    assert 'addItem("UDP", "udp")' in main_window
    assert '"probe-source"' in main_window
    assert "QUrl::FullyEncoded" in main_window
    assert "sourceLabel->setVisible(!streamMode)" in main_window
    assert "sourceButton->setVisible(!streamMode)" in main_window


def test_cpp_application_name_is_online_parcel_flow_monitor():
    main_cpp = read_text(APP_DIR / "src" / "main.cpp")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    runtime_paths = read_text(APP_DIR / "src" / "RuntimePaths.cpp")

    assert "CVDS在线包裹流量监测" in main_cpp
    assert "CVDS在线包裹流量监测" in main_window
    assert "CVDS在线包裹流量监测" in runtime_paths
    assert "CVDS包裹流量检测工具" not in main_cpp
    assert "CVDS包裹流量检测工具" not in main_window
    assert "CVDS包裹流量检测工具" not in runtime_paths


def test_cpp_stitch_a_top_bar_shows_source_channel_clock_and_connection():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    for symbol in [
        "sourceStatusLabel_",
        "channelStatusLabel_",
        "clockLabel_",
        "clockTimer_",
        "refreshRuntimeOverview",
    ]:
        assert symbol in header
        assert symbol in main_window
    assert 'setObjectName("connectionPill")' in main_window
    assert 'setObjectName("runtimeClock")' in main_window
    assert '"通道 --"' in main_window


def test_cpp_jam_controls_and_signal_handling_exist():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "jamSecondsSpin_" in header
    assert "jamSignalPath" in header
    assert '"--jam-seconds"' in main_window
    assert '"--jam-signal-path"' in main_window
    assert 'type == "jam"' in main_window
    assert 'object.value("event_type").toString()' in main_window
    assert 'type == "jam_clear"' in main_window
    assert "堵包" in main_window
    assert "jam_signals.jsonl" in main_window


def test_pt_video_flow_monitor_uses_ultralytics_tracking_and_roi_counting():
    monitor = read_text(APP_DIR / "scripts" / "pt_video_flow_monitor.py")

    assert "from ultralytics import YOLO" in monitor
    assert "model.track" in monitor
    assert "--model" in monitor
    assert "--weights" not in monitor
    assert "--rtsp-transport" in monitor
    assert "CVDS PT 视频检测" not in monitor
    assert 'output_dir / "cvds_online_parcel_flow_monitor.mp4"' in monitor
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
    assert "RegionConfig.cpp" in cmake
    assert "RegionConfig.h" in cmake
    assert "regions.example.json" in cmake
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
    assert "beginModelMetadataRefresh(true)" in start_detection_body
    assert "选择视频后即可绘制" in constructor_body


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


def test_cpp_region_config_supports_strict_json_and_runtime_state():
    header = read_text(APP_DIR / "src" / "RegionConfig.h")
    source = read_text(APP_DIR / "src" / "RegionConfig.cpp")

    assert "struct RegionConfig" in header
    assert "struct RegionRuntimeState" in header
    assert "struct RegionConfigDocument" in header
    assert "QJsonObject" in header
    assert "QJsonParseError" in source
    assert "loadRegionConfigDocument" in header
    assert "saveRegionConfigDocument" in header
    assert "regionConfigDocumentToJson" in header
    assert "regionConfigDocumentFromJson" in header
    assert "regionRuntimeStateToJson" in header
    assert "regionRuntimeStateFromJson" in header
    assert "totalCountRegionId" in header
    assert "throw std::runtime_error" in source
    assert "区域配置缺少 regions" in source
    assert "仅支持 version=1" in source
    assert "主统计区域不存在" in source
    assert "区域 polygon 至少需要 3 个点" in source
    assert "区域 id 重复" in source
    assert "std::floor(number)" in source
    assert "主统计区域必须开启计数" in source
    assert "QSaveFile" in source


def test_cpp_multi_roi_editor_supports_add_rename_delete_save_load():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "addRegion" in header
    assert "renameCurrentRegion" in header
    assert "deleteCurrentRegion" in header
    assert "saveRegionConfig" in header
    assert "loadRegionConfig" in header
    assert "applyRegionSelection" in header
    assert "regionNameEdit_" in header
    assert "regionCombo_" in header
    assert "totalCountRegionCombo_" in header
    assert "新增区域" in main_window
    assert "重命名区域" in main_window
    assert "删除区域" in main_window
    assert "保存区域配置" in main_window
    assert "加载区域配置" in main_window
    assert "主统计区域" in main_window
    assert "主统计区域必须参与累计" in main_window
    assert "totalCountRegionId_ == currentRegionId_ && !checked" in main_window
    assert "RuntimePaths::regionsExamplePath()" in main_window
    assert "QFileDialog::getOpenFileName(" in main_window
    assert '"加载区域配置"' in main_window


def test_cpp_preview_label_supports_multiple_flow_regions_and_active_region_highlight():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "setFlowRegions" in header
    assert "setActiveRegionId" in header
    assert "flowRegions_" in header
    assert "activeRegionId_" in header
    assert "flowRegionChanged" in header
    assert "flowRegionChanged(const QString& regionId, const QVector<QPoint>& polygon, bool closed)" in header
    assert "regions_[index].polygon = polygon;" in main_window
    assert "当前区域" in main_window
    assert "drawPolygon(painter, region.polygon" in main_window
    assert '"区域 "' not in header


def test_cpp_startup_does_not_restore_saved_regions():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    constructor = main_window.split("MainWindow::MainWindow(QWidget* parent)")[1].split("MainWindow::~MainWindow()")[0]

    assert "loadRegionConfigDocument" not in constructor
    assert "restoreRegionConfigDocument" not in constructor
    assert "regions_.clear();" in constructor
    assert "ensureDefaultRegion();" in constructor


def test_cpp_dashboard_has_kpi_region_table_and_flash_timer():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert "QTableWidget" in header
    assert "QTimer" in header
    assert "updateDashboard" in header
    assert "setDashboardAlarmActive" in header
    assert "flashTimer_" in header
    assert "kpiTotalCountValueLabel_" in header
    assert "kpiStatusValueLabel_" in header
    assert "kpiInsideCountValueLabel_" in header
    assert "kpiJamCountValueLabel_" in header
    assert "dashboardRoot_" in header
    assert "updateAlertStyle" in header
    assert "区域状态" in main_window
    assert "累计包裹" in main_window
    assert "当前状态" in main_window
    assert "堵包秒数" in main_window
    assert "QTableWidget" in main_window
    assert "new QTableWidget(0, 6" in main_window
    assert "setInterval(500)" in main_window
    assert "dashboardRoot_->setStyleSheet" in main_window
    assert "dashboardStatusForStates" in main_window
    assert 'object.value("regions").toArray()' in main_window
    assert 'object.value("global_status").toString()' in main_window
    assert 'object.value("total_count").toInt()' in main_window
    assert "state.id == totalCountRegionId_" in main_window


def test_cpp_window_shutdown_waits_for_detection_thread():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    destructor = main_window.split("MainWindow::~MainWindow()")[1].split("QWidget* MainWindow::buildPathPanel()")[0]

    assert "stopDetection();" in destructor
    assert "stopVideoPreview();" in destructor
    assert "previewThread_->wait();" in destructor
    assert "workerThread_->quit();" in destructor
    assert "workerThread_->wait();" in destructor


def test_cpp_does_not_persist_camera_password_or_authenticated_rtsp_url():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    load_settings = main_window.split("void MainWindow::loadSettings()")[1].split("void MainWindow::saveSettings()")[0]
    save_settings = main_window.split("void MainWindow::saveSettings() const")[1].split("void MainWindow::populateClassCombo")[0]

    assert 'settings.remove("hikvisionPassword")' in load_settings
    assert 'settings.value("hikvisionPassword"' not in load_settings
    assert 'settings.setValue("hikvisionPassword"' not in save_settings
    assert "sourcePathForSettings" in save_settings
    assert "QUrl::RemoveUserInfo" in main_window


def test_cpp_worker_helper_processes_have_timeouts_and_worker_is_deleted_with_thread():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    metadata = main_window.split("void MainWindow::refreshModelMetadata()")[1].split("void MainWindow::runEnvironmentDiagnose()")[0]
    diagnose = main_window.split("void MainWindow::runEnvironmentDiagnose()")[1].split("void MainWindow::detectionFinished")[0]
    cleanup = main_window.split("void MainWindow::cleanupWorker()")[1].split("void MainWindow::setDashboardAlarmActive")[0]

    assert "loadedModelPath_" in header
    assert "loadedModelPath_ == modelPath" in metadata
    assert "QTimer::singleShot(30000" in metadata
    assert "process->kill();" in metadata
    assert "waitForFinished(30000)" not in metadata
    assert "waitForFinished(30000)" in diagnose
    assert "process.kill();" in diagnose
    assert "QThread::finished, worker_, &QObject::deleteLater" in main_window
    assert "worker_->deleteLater();" not in cleanup


def test_release_script_supports_isolated_2_0_directory_and_onedir_worker():
    build_script = read_text(APP_DIR / "packaging" / "build_release.ps1")

    assert '[string]$DistName = "CVDS_Package_Flow_Detector"' in build_script
    assert '[switch]$SkipInstaller' in build_script
    assert 'Join-Path $RootDir "dist\\$DistName"' in build_script
    assert "--onedir" in build_script
    assert "--onefile" not in build_script
    assert "Invoke-Checked" in build_script
    assert "Set-Content -Encoding UTF8" in build_script


def test_cpp_window_title_displays_release_version():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")

    assert 'setWindowTitle("CVDS在线包裹流量监测 " + RuntimePaths::versionText())' in main_window


def test_cpp_locks_configuration_while_detection_is_running_and_resets_loaded_dashboard():
    header = read_text(APP_DIR / "src" / "MainWindow.h")
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    restore = main_window.split("void MainWindow::restoreRegionConfigDocument")[1].split("void MainWindow::populateClassCombo")[0]

    assert "setConfigurationEditingEnabled" in header
    assert "pathPanel_" in header
    assert "paramPanel_" in header
    assert "roiPanel_" in header
    assert "setConfigurationEditingEnabled(false);" in main_window
    assert "setConfigurationEditingEnabled(true);" in main_window
    assert "setDashboardAlarmActive(false);" in restore
    assert "regionRuntimeStates_.clear();" in restore
    assert 'dashboardStatusText_ = "待机";' in restore


def test_cpp_deleting_primary_region_selects_another_counting_region():
    main_window = read_text(APP_DIR / "src" / "MainWindow.cpp")
    delete_region = main_window.split("void MainWindow::deleteCurrentRegion()")[1].split("void MainWindow::saveRegionConfig()")[0]

    assert "nextTotalCountRegionId" in delete_region
    assert "countEnabled" in delete_region
    assert "没有可作为主统计区域的计数区域" in delete_region


def test_cpp_region_json_rejects_integers_outside_qt_int_range():
    source = read_text(APP_DIR / "src" / "RegionConfig.cpp")

    assert "#include <limits>" in source
    assert "std::numeric_limits<int>::min()" in source
    assert "std::numeric_limits<int>::max()" in source
