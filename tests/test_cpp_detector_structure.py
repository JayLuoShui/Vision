from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CPP_APP = ROOT / "apps" / "cvds_cpp_detector"
WCS_APP = ROOT / "apps" / "CVDS_WCS_Multi_Camera_Monitor"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_wcs_openvino_app_files_exist():
    expected = [
        WCS_APP / "CMakeLists.txt",
        WCS_APP / "README.md",
        WCS_APP / "src" / "main.cpp",
        WCS_APP / "src" / "MainWindow.cpp",
        WCS_APP / "include" / "MainWindow.h",
        WCS_APP / "src" / "inference" / "OpenVinoDetector.h",
        WCS_APP / "src" / "inference" / "OpenVinoDetector.cpp",
        WCS_APP / "src" / "inference" / "LetterBox.h",
        WCS_APP / "src" / "inference" / "LetterBox.cpp",
        WCS_APP / "src" / "inference" / "YoloPostprocess.h",
        WCS_APP / "src" / "inference" / "YoloPostprocess.cpp",
        WCS_APP / "src" / "tracking" / "ByteTrack.h",
        WCS_APP / "src" / "tracking" / "ByteTrack.cpp",
        WCS_APP / "src" / "tracking" / "KalmanFilter.h",
        WCS_APP / "src" / "tracking" / "HungarianMatcher.h",
        WCS_APP / "src" / "tracking" / "Track.h",
        WCS_APP / "src" / "pipeline" / "VideoPipeline.h",
        WCS_APP / "src" / "pipeline" / "VideoPipeline.cpp",
        WCS_APP / "src" / "pipeline" / "FlowCounter.h",
        WCS_APP / "src" / "pipeline" / "JamDetector.h",
        WCS_APP / "src" / "pipeline" / "ResultWriter.h",
        WCS_APP / "src" / "utils" / "Geometry.h",
        WCS_APP / "src" / "utils" / "FpsMeter.h",
        WCS_APP / "configs" / "cameras.json",
        WCS_APP / "configs" / "wcs.json",
        WCS_APP / "configs" / "runtime.json",
    ]
    missing = [str(path) for path in expected if not path.exists()]
    assert missing == []


def test_wcs_cmake_links_openvino_and_does_not_copy_python_runtime():
    cmake = read_text(WCS_APP / "CMakeLists.txt")
    assert "find_package(OpenVINO REQUIRED COMPONENTS Runtime)" in cmake
    assert "openvino::runtime" in cmake
    assert "find_package(OpenCV REQUIRED COMPONENTS core imgproc videoio imgcodecs dnn)" in cmake
    assert "$<TARGET_RUNTIME_DLLS:CVDS_WCS_Multi_Camera_Monitor>" in cmake
    assert "openvino*.dll" in cmake
    assert "opencv*.dll" in cmake
    forbidden = ["worker_entry.py", "pt_video_flow_monitor.py", "gpu_infer_worker.py", "PyInstaller", "PATTERN \"*.pt\"", "PATTERN \"*.onnx\""]
    for token in forbidden:
        assert token not in cmake


def test_cpp_detector_cmake_no_longer_installs_python_worker_or_runtime_pt_onnx():
    cmake = read_text(CPP_APP / "CMakeLists.txt")
    assert "find_package(OpenVINO REQUIRED COMPONENTS Runtime)" in cmake
    assert "openvino::runtime" in cmake
    assert "CVDS_ENABLE_TENSORRT" in cmake
    assert "NvInfer" in cmake
    assert "src/inference/OpenVinoDetector.cpp" in cmake
    assert "src/inference/TensorRtDetector.cpp" in cmake
    assert "src/inference/DetectorBackend.cpp" in cmake
    assert "src/tracking/ByteTrack.cpp" in cmake
    assert "src/pipeline/VideoPipeline.cpp" in cmake
    assert "src/utils/Geometry.cpp" in cmake
    for token in ["worker_entry.py", "inspect_model_metadata.py", "pt_video_flow_monitor.py", "DIRECTORY scripts", "PATTERN \"*.pt\"", "PATTERN \"*.onnx\""]:
        assert token not in cmake


def test_cpp_detector_has_native_openvino_pipeline_modules():
    expected = [
        CPP_APP / "src" / "inference" / "OpenVinoDetector.h",
        CPP_APP / "src" / "inference" / "OpenVinoDetector.cpp",
        CPP_APP / "src" / "inference" / "TensorRtDetector.h",
        CPP_APP / "src" / "inference" / "TensorRtDetector.cpp",
        CPP_APP / "src" / "inference" / "DetectorBackend.h",
        CPP_APP / "src" / "inference" / "DetectorBackend.cpp",
        CPP_APP / "src" / "inference" / "LetterBox.h",
        CPP_APP / "src" / "inference" / "LetterBox.cpp",
        CPP_APP / "src" / "inference" / "YoloPostprocess.h",
        CPP_APP / "src" / "inference" / "YoloPostprocess.cpp",
        CPP_APP / "src" / "tracking" / "ByteTrack.h",
        CPP_APP / "src" / "tracking" / "ByteTrack.cpp",
        CPP_APP / "src" / "tracking" / "KalmanFilter.h",
        CPP_APP / "src" / "tracking" / "KalmanFilter.cpp",
        CPP_APP / "src" / "tracking" / "HungarianMatcher.h",
        CPP_APP / "src" / "tracking" / "HungarianMatcher.cpp",
        CPP_APP / "src" / "tracking" / "Track.h",
        CPP_APP / "src" / "tracking" / "Track.cpp",
        CPP_APP / "src" / "pipeline" / "VideoPipeline.h",
        CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp",
        CPP_APP / "src" / "pipeline" / "FlowCounter.h",
        CPP_APP / "src" / "pipeline" / "FlowCounter.cpp",
        CPP_APP / "src" / "pipeline" / "JamDetector.h",
        CPP_APP / "src" / "pipeline" / "JamDetector.cpp",
        CPP_APP / "src" / "pipeline" / "ResultWriter.h",
        CPP_APP / "src" / "pipeline" / "ResultWriter.cpp",
        CPP_APP / "src" / "utils" / "Geometry.h",
        CPP_APP / "src" / "utils" / "Geometry.cpp",
        CPP_APP / "src" / "utils" / "JsonlWriter.h",
        CPP_APP / "src" / "utils" / "JsonlWriter.cpp",
        CPP_APP / "src" / "utils" / "FpsMeter.h",
        CPP_APP / "src" / "utils" / "FpsMeter.cpp",
    ]
    assert [str(path) for path in expected if not path.exists()] == []


def test_cpp_detector_main_window_uses_native_pipeline_without_worker_process():
    header = read_text(CPP_APP / "src" / "MainWindow.h")
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    assert '#include "pipeline/VideoPipeline.h"' in header
    assert "VideoPipeline* pipeline_" in header
    assert "new VideoPipeline" in source
    assert "QThread" in header
    forbidden = [
        "class DetectionWorker",
        "workerPath",
        "RuntimePaths::workerExePath",
        "cvds_detector_worker.exe",
        "inspect-model",
        "QProcess process",
    ]
    for token in forbidden:
        assert token not in header + source


def test_cpp_detector_startup_does_not_scan_weights_for_default_model():
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    assert "resolveDefaultModelPath" in source
    assert "setPrivatePath(modelEdit_, findDefaultModelPath())" not in source
    assert 'settings.value("lastModelPath").toString()' in source
    assert "if (privatePath(modelEdit_).trimmed().isEmpty())" in source


def test_cpp_detector_release_package_has_no_python_runtime_artifacts():
    script = read_text(CPP_APP / "packaging" / "build_release.ps1")
    cmake = read_text(CPP_APP / "CMakeLists.txt")
    combined = script + cmake
    for token in [
        "requirements-worker.txt",
        "worker_entry.py",
        "pt_video_flow_monitor.py",
        "cvds_detector_worker.exe",
        "PyInstaller",
        "conda",
        "torch",
        "ultralytics",
    ]:
        assert token.lower() not in combined.lower()
    assert "opencv_java" in combined


def test_cpp_detector_ui_accepts_openvino_ir_and_openvino_devices_only():
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    header = read_text(CPP_APP / "src" / "MainWindow.h")
    assert "OpenVINO IR (*.xml)" in source
    assert "TensorRT Engine (*.engine *.plan)" in source
    assert 'addItem("OpenVINO"' in source
    assert 'addItem("TensorRT"' in source
    assert "refreshDeviceOptions" in header
    assert "refreshDeviceOptions(savedDevice)" in source
    assert "OpenVINO GPU（Intel）" in source
    assert "NVIDIA CUDA GPU 0" in source
    for device in ['addItem("AUTO"', 'addItem("CPU"', 'addItem("OpenVINO GPU（Intel）"']:
        assert device in source
    assert 'addItem("NPU"' not in source
    assert 'addItem("CUDA"' not in source
    for token in ["*.pt", "*.onnx", 'addItem("0"']:
        assert token not in source


def test_cpp_detector_pipeline_selects_openvino_or_tensorrt_backend():
    header = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.h")
    source = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    backend_header = read_text(CPP_APP / "src" / "inference" / "DetectorBackend.h")
    backend_source = read_text(CPP_APP / "src" / "inference" / "DetectorBackend.cpp")
    trt_source = read_text(CPP_APP / "src" / "inference" / "TensorRtDetector.cpp")

    assert "DetectorBackend detector_" in header
    assert "InferenceBackend backend" in header
    assert "config_.backend" in source
    assert "TensorRt" in backend_header
    assert "CVDS_WITH_TENSORRT" in trt_source
    assert "tensorRt_.load(modelPath, device" in backend_source
    assert "cudaSetDevice" in trt_source
    assert "enqueueV3" in trt_source
    assert "deserializeCudaEngine" in trt_source


def test_cpp_detector_tensorrt_backend_handles_metadata_and_multiple_outputs():
    source = read_text(CPP_APP / "src" / "inference" / "TensorRtDetector.cpp")
    assert "metadata.yaml" in source
    assert "YoloOutputLayout::EndToEnd" in source
    assert "outputBindings" in source
    assert "parseOutputBinding" in source
    assert "getTensorDataType" in source


def test_cpp_detector_overlay_uses_ascii_region_id_for_opencv_text():
    source = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    assert "overlayRegionLabel" in source
    assert "(state.name + \": \"" not in source


def test_cpp_detector_target_box_color_follows_flow_roi_center_state():
    source = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    assert "trackCenterInsideFlowRegion" in source
    assert "const cv::Scalar boxColor = insideFlowRoi" in source
    assert "cv::Scalar(0, 220, 0)" in source
    assert "cv::Scalar(0, 220, 255)" in source
    assert "Geometry::boxCenter(detection.box)" in source


def test_cpp_detector_dashboard_stats_are_throttled_without_delaying_jam_events():
    source = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    header = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.h")
    assert "emitStatsPayload(" in header
    assert "statsEvery" in source
    assert "if (frameIndex == 1 || frameIndex % statsEvery == 0 || !jamEvents.isEmpty())" in source
    assert "emitFramePayload(frameIndex, matToImage(overlay))" in source
    assert "emitDashboard(payload);" in source


def test_cpp_detector_jam_clear_forces_preview_refresh_and_clears_alarm_regions():
    pipeline = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    window = read_text(CPP_APP / "src" / "MainWindow.cpp")
    assert "const bool forcePreview = !jamEvents.isEmpty()" in pipeline
    assert "if (forcePreview || frameIndex == 1 || frameIndex % previewEvery == 0)" in pipeline
    assert "previewLabel_->setJamRegionIds({});" in window
    refresh_table = window[window.index("void MainWindow::refreshRegionTable") :]
    assert "const bool alertVisible = dashboardJamActive_ && dashboardFlashVisible_;" in refresh_table
    assert "previewLabel_->setAlertFlashVisible(alertVisible);" in refresh_table
    update_style = window[window.index("void MainWindow::updateAlertStyle") :]
    assert "if (!dashboardJamActive_ || !dashboardFlashVisible_) {" in update_style
    assert "QWidget#dashboardRoot QFrame#monitorPanel{background:#080D13;border:1px solid #263746;border-radius:3px;}" in update_style
    assert "QWidget#dashboardRoot QFrame#dashboardCard{background:#111B25;border:1px solid #263746;border-left:2px solid #2F88F5;border-radius:3px;}" in update_style
    toggle_flash = window[window.index("void MainWindow::toggleAlarmFlash") :]
    assert "if (!dashboardJamActive_) {" in toggle_flash


def test_cpp_detector_hides_region_table_until_roi_is_closed():
    window = read_text(CPP_APP / "src" / "MainWindow.cpp")
    refresh_region_table = window[window.index("void MainWindow::refreshRegionTable") :]
    assert "const int displayRowCount = runtimeRowCount > 0 ? runtimeRowCount : (hasConfiguredRegion ? regions_.size() : 0);" in refresh_region_table
    assert "regionTable_->setRowCount(displayRowCount);" in refresh_region_table


def test_cpp_detector_supports_multiple_native_video_pipelines():
    header = read_text(CPP_APP / "src" / "MainWindow.h")
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    assert "multiSourceEdit_" in header
    assert "multiHikChannelEdit_" in header
    assert "pipelineRuntimes_" in header
    assert "previewRuntimes_" in header
    assert "startConfiguredPipelines" in header
    assert "configuredSourcePaths" in header
    assert "configuredHikvisionChannels" in header
    assert "cleanupPreview" in header
    assert "composeMultiCameraPreview" in header
    assert "multiSourceEdit_ = new QPlainTextEdit" in source
    assert "multiHikChannelEdit_ = new QLineEdit" in source
    assert "多路通道" in source
    assert "configuredSourcePaths()" in source
    assert "configuredHikvisionChannels()" in source
    assert "buildHikvisionRtsp(channel)" in source
    assert 'settings.value("hikvisionPassword"' in source
    assert 'settings.setValue("hikvisionPassword", hikPasswordEdit_->text())' in source
    assert 'settings.remove("hikvisionPassword")' not in source
    assert "海康密码不能为空" in source
    assert "streamLayout->addWidget(hikIpEdit_, 0, 1)" in source
    assert "streamLayout->addWidget(hikRtspPortEdit_, 1, 1)" in source
    assert "leftShell->setMinimumWidth(320)" in source
    assert "leftShell->setMaximumWidth(320)" in source
    assert "const int leftWidth = 320" in source
    assert "configurePortLineEdit(hikRtspPortEdit_)" in source
    assert "configureAdaptiveLineEdit(hikUserEdit_, 8, 16)" in source
    assert "configureAdaptiveLineEdit(hikPasswordEdit_, 10, 20)" in source
    assert "streamLayout->setColumnStretch(1, 1)" in source
    configured_sources = source[
        source.index("QStringList MainWindow::configuredSourcePaths() const") :
        source.index("QVector<int> MainWindow::configuredHikvisionChannels() const")
    ]
    assert "if (streamMode) {" in configured_sources
    assert configured_sources.index("if (streamMode) {") < configured_sources.index("privatePath(sourceEdit_)")
    assert "return sources;" in configured_sources[
        configured_sources.index("if (streamMode) {") : configured_sources.index("privatePath(sourceEdit_)")
    ]
    assert 'QDir(config.outputDir).filePath(QString("camera_%1").arg(index + 1))' in source
    assert "config.previewFps = std::min(config.previewFps, 8);" not in source
    assert "new VideoPipeline(config)" in source
    assert "connect(pipeline, &VideoPipeline::done, pipeline, &QObject::deleteLater)" in source
    assert "connect(pipeline, &VideoPipeline::failed, pipeline, &QObject::deleteLater)" in source
    assert "connect(thread, &QThread::finished, pipeline, &QObject::deleteLater)" not in source
    assert "new VideoPreviewWorker(source, transport)" in source
    assert "for (int index = 0; index < sources.size(); ++index)" in source
    assert "connect(worker, &VideoPreviewWorker::frameReady, this, [this, cameraId]" in source
    assert "applyLocalVideoSources" in header
    assert "应用本地视频" in source
    apply_local = source[
        source.index("void MainWindow::applyLocalVideoSources()") :
        source.index("void MainWindow::applyHikvisionStream()")
    ]
    assert "regions_.clear();" in apply_local
    assert "ensureDefaultRegion();" in apply_local
    assert "previewLabel_->setDetectRoiFromText({});" in apply_local
    assert "loadConfiguredVideoPreviewFrames(sources);" in apply_local
    assert "startVideoPreview();" not in apply_local
    assert "loadConfiguredVideoPreviewFrames" in header
    load_settings = source[
        source.index("void MainWindow::loadSettings()") :
        source.index("void MainWindow::saveSettings() const")
    ]
    save_settings = source[
        source.index("void MainWindow::saveSettings() const") :
        source.index("void MainWindow::setRoiDrawMode")
    ]
    assert "setPrivatePath(sourceEdit_, {})" in load_settings
    assert 'settings.remove("lastSourcePath")' in save_settings
    assert 'settings.remove("multiSourcePaths")' in save_settings
    assert 'settings.value("multiSourcePaths")' not in source
    assert 'settings.setValue("multiSourcePaths"' not in source
    browse_source = source[
        source.index("void MainWindow::browseSource()") :
        source.index("void MainWindow::applyLocalVideoSources()")
    ]
    assert "multiSourceEdit_->appendPlainText(path);" in browse_source
    assert "setText(\"已加入多路视频源\")" in browse_source
    assert "setMinimumWidth(0)" in browse_source
    assert "setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed)" in browse_source
    assert "setPrivatePath(sourceEdit_, path, true)" not in browse_source
    assert "sourceModeCombo_->setCurrentIndex(sourceModeCombo_->findData(\"file\"));" in source
    assert "constexpr int previewIntervalMs = 33" in source
    assert "constexpr int previewIntervalMs = 125" not in source
    assert "previewComposePending_" in header
    assert "QTimer::singleShot(100, this, [this]()" in source
    first_frame_preview = source[
        source.index("void MainWindow::loadConfiguredVideoPreviewFrames") :
        source.index("void MainWindow::loadVideoPreviewFrame")
    ]
    assert "cameraFrames_.clear();" in first_frame_preview
    assert "capture.read(frame)" in first_frame_preview
    assert "composeMultiCameraPreview();" in first_frame_preview
    assert "new VideoPreviewWorker" not in first_frame_preview
    assert "logEdit_->setMaximumBlockCount(800)" in source
    preview_open_capture = source[
        source.index("cv::VideoCapture openCapture") :
        source.index("QString findDefaultModelPath")
    ]
    preview_open_params = preview_open_capture[
        preview_open_capture.index("const std::vector<int> params") :
        preview_open_capture.index("cv::VideoCapture capture")
    ]
    assert "cv::CAP_PROP_BUFFERSIZE, 1" not in preview_open_params
    assert "capture.set(cv::CAP_PROP_BUFFERSIZE, 1)" in preview_open_capture
    assert "previewSourceLabel" in source
    assert "视频预览失败（%2）：%3" in source
    pipeline = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    assert "capture->set(cv::CAP_PROP_BUFFERSIZE, 1)" in pipeline
    assert "connect(pipeline, &VideoPipeline::frameReady, this, [this, cameraId]" in source
    assert "composeMultiCameraPreview()" in source
    assert "QProcess" not in source


def test_cpp_detector_multi_camera_rois_and_count_scope_are_camera_aware():
    header = read_text(CPP_APP / "src" / "MainWindow.h")
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    flow_counter = read_text(CPP_APP / "src" / "pipeline" / "FlowCounter.cpp")
    region_config = read_text(CPP_APP / "src" / "RegionConfig.cpp")
    pipeline = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")

    assert "__all_count_regions__" in source
    assert 'region.id = "region_1"' in source
    assert 'region.name = "区域 1"' in source
    assert 'region.name = "主统计区域"' not in source
    assert '"当前区域: " + activeRegionId_' not in source
    assert "__all_count_regions__" in flow_counter
    assert "__all_count_regions__" in region_config
    assert "多区域汇总" in source
    assert "regionDocumentForCamera" in header
    assert "mapRegionToCameraFrame" in source
    assert "cameraImageRects_" in header
    assert "cameraSourceSizes_" in header
    assert "config.regions = regionDocumentForCamera(cameraId, multiCamera)" in source
    assert "cameraImageRects_.contains(cameraId)" in source
    assert "多路 ROI 尚未完成画面归属" in source
    assert "if (!document.regions.isEmpty() && !regionIds.contains(document.totalCountRegionId))" in source
    assert "document.totalCountRegionId = QStringLiteral(\"__all_count_regions__\")" in source
    assert "connect(pipeline, &VideoPipeline::dashboardPayloadReady, this, [this, cameraId]" in source
    assert "updateDashboardForCamera(cameraId, payload)" in source
    assert "cameraRegionRuntimeStates_" in header
    assert "dashboardRuntimeStates_" in header
    assert "aggregateDashboardFromCameraStates" in header
    assert "regionRuntimeStates_.push_back(displayState)" in source
    assert "dashboardRuntimeStates_.push_back(state)" in source
    assert "dashboardJamActive_ = dashboardJamActive_ || state.jamActive;" in source
    assert source.index("dashboardJamActive_ = dashboardJamActive_ || state.jamActive;") < source.index("if (!stateMatchesKpiRegion) {")
    assert "const bool stateMatchesKpiRegion" in source
    assert "if (!stateMatchesKpiRegion) {" in source
    assert "kpiRegionId == QStringLiteral(\"__all_count_regions__\")" in source
    assert "const QString kpiRegionId = totalCountRegionId_" in source
    assert "dashboardSelectedCameraOnly" not in source
    count_scope_handler = source[
        source.index("connect(totalCountRegionCombo_") :
        source.index("connect(regionNameEdit_")
    ]
    assert "aggregateDashboardFromCameraStates();" in count_scope_handler
    assert "setDashboardAlarmActive(dashboardJamActive_);" in count_scope_handler
    assert "totalRegionId_ == QStringLiteral(\"__all_count_regions__\")" in flow_counter
    assert "totalRegionIsAll" in region_config
    assert "totalAll" in pipeline


def test_cpp_detector_clicking_camera_tile_only_selects_roi_before_detection():
    header = read_text(CPP_APP / "src" / "MainWindow.h")
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")

    assert "void imageClicked(const QPoint& imagePoint)" in header
    assert "selectCameraAtPoint" in header
    assert "selectDrawingRegionForCamera" in header
    assert "isDetectionRunning" in header
    assert "emit imageClicked(labelToImagePoint(event->pos()))" in source
    assert "connect(previewLabel_, &RoiPreviewLabel::imageClicked" in source
    assert "cameraImageRects_.value(cameraId).contains(imagePoint)" in source
    assert "if (!isDetectionRunning())" in source
    assert "selectDrawingRegionForCamera(cameraId)" in source
    assert "return;" in source[
        source.index("void MainWindow::selectCameraAtPoint") :
        source.index("void MainWindow::selectDrawingRegionForCamera")
    ]
    assert "!region.polygon.isEmpty() && cameraRect.contains(polygonCenter(region.polygon))" in source
    assert "RegionConfig region;" in source
    assert "region.id = nextRegionId();" in source
    assert "dashboardStatusForStates(dashboardRuntimeStates_" in source
    assert "const int runtimeRowCount = isDetectionRunning() && !regionRuntimeStates_.isEmpty()" in source
    assert "config.previewFps = std::min(config.previewFps, 8);" not in source
    assert "constexpr int previewIntervalMs = 33" in source
    assert "constexpr int previewIntervalMs = 125" not in source


def test_cpp_detector_multi_camera_preview_has_no_top_glass_overlay():
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    compose = source[
        source.index("void MainWindow::composeMultiCameraPreview()") :
        source.index("void MainWindow::setConfigurationEditingEnabled")
    ]
    assert "painter.fillRect(QRect(cell.left(), cell.top(), cell.width(), 28)" not in compose
    assert "painter.drawText(cell.adjusted" not in compose
    assert "QColor(5, 9, 18, 190)" not in compose
    assert "painter.drawImage(topLeft, scaled)" in compose
    assert "cameraImageRects_.insert(cameraId" in compose


def test_cpp_detector_skips_low_information_hikvision_frames():
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    pipeline = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")

    assert "isLowInformationFrame" in source
    assert "isLowInformationFrame" in pipeline
    assert "cv::meanStdDev" in source
    assert "cv::meanStdDev" in pipeline
    assert "if (canBeRuntimeSource(source_) && isLowInformationFrame(frame))" in source
    assert "continue;" in source[source.index("void VideoPreviewWorker::run()") : source.index("void VideoPreviewWorker::stop()")]
    assert "if (isLiveSource(config_.sourcePath) && isLowInformationFrame(*frame))" in pipeline
    assert "attempt < maxAttempts" in pipeline
    assert "视频流连续输出低信息异常帧" not in pipeline


def test_cpp_detector_roi_editor_current_region_label_is_top_right():
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    assert '"当前区域: " + activeRegionName' not in source
    assert "painter.drawText(imageRect.adjusted(12, 18, -12, -18)" not in source


def test_cpp_detector_bytetrack_is_wired_and_implemented_in_cpp():
    header = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.h")
    pipeline = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    bytetrack = read_text(CPP_APP / "src" / "tracking" / "ByteTrack.cpp")

    assert "ByteTrack tracker_" in header
    assert "tracker_.update(detections" in pipeline
    assert "flowCounter_.update(tracks)" in pipeline
    assert "jamDetector_.update(states, tracker_.tracks()" in pipeline
    assert "highDetections" in bytetrack
    assert "lowDetections" in bytetrack
    assert "hungarianMatch" in bytetrack
    assert "filter.predict" in bytetrack
    assert "filter.update" in bytetrack


def test_cpp_detector_bytetrack_thresholds_follow_ultralytics_defaults():
    pipeline = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    header = read_text(CPP_APP / "src" / "tracking" / "ByteTrack.h")
    source = read_text(CPP_APP / "src" / "tracking" / "ByteTrack.cpp")

    assert "configureTracker()" in pipeline
    assert "newTrackConfidence" in header
    assert "newTrackConfidence_" in source
    assert "lowMatchIou = 0.5f" in header
    assert "detections[index].confidence >= newTrackConfidence_" in source
    assert "track.missed == 1" in source


def test_cpp_detector_openvino_seg_end2end_does_not_treat_mask_coefficients_as_classes():
    detector = read_text(CPP_APP / "src" / "inference" / "OpenVinoDetector.cpp")
    post_header = read_text(CPP_APP / "src" / "inference" / "YoloPostprocess.h")
    post_source = read_text(CPP_APP / "src" / "inference" / "YoloPostprocess.cpp")

    assert "metadata.yaml" in detector
    assert "end2end:" in detector
    assert "YoloOutputLayout::EndToEnd" in detector
    assert "outputLayout" in post_header
    assert "attrs >= 6" in post_source
    assert "mask coefficients" in post_source


def test_cpp_detector_native_pipeline_preserves_outputs_and_jam_signals():
    writer = read_text(CPP_APP / "src" / "pipeline" / "ResultWriter.cpp")
    jam = read_text(CPP_APP / "src" / "pipeline" / "JamDetector.cpp")
    for filename in [
        "cvds_online_parcel_flow_monitor.mp4",
        "flow_events.csv",
        "jam_signals.jsonl",
        "flow_summary.json",
        "cvds_preview.jpg",
    ]:
        assert filename in writer
    assert "IO_JAM_ON" in writer
    assert "IO_JAM_OFF" in writer
    assert "speedPixelsPerSecond" in jam
    assert "insideCount > 0" in jam


def test_cpp_detector_release_script_packages_native_runtimes_only():
    script = read_text(CPP_APP / "packaging" / "build_release.ps1")
    cmake = read_text(CPP_APP / "CMakeLists.txt")
    assert "apps\\cvds_cpp_detector" in script
    assert "CVDS_Cpp_Detector.exe" in script
    assert "openvino*.dll" in script
    assert "openvino_ir_frontend.dll" in script
    assert "intel_npu" in script
    assert "openvino_auto_batch_plugin" in script
    assert "openvino_hetero_plugin" in script
    assert "_intel_npu" not in cmake
    assert "_auto_batch_plugin" not in cmake
    assert "_hetero_plugin" not in cmake
    assert "nvinfer*.dll" in script
    assert "opencv*.dll" in script
    assert "opencv_java" in script
    assert "^nvinfer_[0-9]+\\.dll$" in script
    assert "nvinfer_builder_resource" in script
    assert "nvinfer_builder_resource" in cmake
    assert "nvonnxparser*.dll" not in script
    for token in ["PyInstaller", "requirements-worker.txt", "cvds_detector_worker.exe", "conda", "torch", "ultralytics"]:
        assert token.lower() not in script.lower()


def test_cpp_detector_readmes_document_native_openvino_ir_only():
    combined = read_text(CPP_APP / "README.md") + read_text(CPP_APP / "README_RELEASE.md")
    assert "纯 C++ OpenVINO Runtime" in combined
    assert "TensorRT" in combined
    assert ".engine" in combined
    assert ".xml + .bin" in combined
    assert "AUTO / CPU / GPU" in combined
    assert "AUTO / CPU / GPU / NPU" not in combined
    for token in ["支持 PT", "支持 ONNX", "PT、ONNX", "worker 命令"]:
        assert token not in combined


def test_wcs_readme_documents_openvino_ir_runtime_only():
    readme = read_text(WCS_APP / "README.md")
    assert "纯 C++ OpenVINO Runtime" in readme
    assert ".xml + .bin" in readme
    assert "OpenVINO 模型目录" in readme
    assert "cvds_online_parcel_flow_monitor.mp4" in readme
    assert "flow_events.csv" in readme
    assert "jam_signals.jsonl" in readme
    assert "flow_summary.json" in readme
    assert "cvds_preview.jpg" in readme
    assert "IO_JAM_ON" in readme
    assert "IO_JAM_OFF" in readme


def test_wcs_python_worker_wrapper_removed():
    assert not (WCS_APP / "scripts" / "gpu_infer_worker.py").exists()


def test_wcs_main_window_uses_split_layout_and_toggleable_settings_panel():
    header = read_text(WCS_APP / "include" / "MainWindow.h")
    source = read_text(WCS_APP / "src" / "MainWindow.cpp")
    assert "QSplitter" in header
    assert "settingsToggleButton_" in header
    assert 'QSplitter(Qt::Horizontal' in source
    assert '收起控制面板' in source
    assert '展开控制面板' in source
