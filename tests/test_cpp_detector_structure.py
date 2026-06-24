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
    assert "OpenVINO IR (*.xml)" in source
    assert "TensorRT Engine (*.engine *.plan)" in source
    assert 'addItem("OpenVINO"' in source
    assert 'addItem("TensorRT"' in source
    for device in ['addItem("AUTO"', 'addItem("CPU"', 'addItem("GPU"', 'addItem("NPU"']:
        assert device in source
    assert 'addItem("CUDA"' in source
    for token in ["*.pt", "*.onnx", 'addItem("0"']:
        assert token not in source


def test_cpp_detector_pipeline_selects_openvino_or_tensorrt_backend():
    header = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.h")
    source = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    backend_header = read_text(CPP_APP / "src" / "inference" / "DetectorBackend.h")
    trt_source = read_text(CPP_APP / "src" / "inference" / "TensorRtDetector.cpp")

    assert "DetectorBackend detector_" in header
    assert "InferenceBackend backend" in header
    assert "config_.backend" in source
    assert "TensorRt" in backend_header
    assert "CVDS_WITH_TENSORRT" in trt_source
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


def test_cpp_detector_dashboard_stats_are_emitted_every_frame_without_preview_delay():
    source = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.cpp")
    header = read_text(CPP_APP / "src" / "pipeline" / "VideoPipeline.h")
    assert "emitStatsPayload(" in header
    assert "emitStatsPayload(frameIndex, states, static_cast<int>(tracks.size()))" in source
    assert "emitFramePayload(frameIndex, matToImage(overlay))" in source
    assert "emitDashboard(payload);" in source


def test_cpp_detector_roi_editor_current_region_label_is_top_right():
    source = read_text(CPP_APP / "src" / "MainWindow.cpp")
    assert 'Qt::AlignRight | Qt::AlignTop, "当前区域: " + activeRegionId_' in source


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
    assert "apps\\cvds_cpp_detector" in script
    assert "CVDS_Cpp_Detector.exe" in script
    assert "openvino*.dll" in script
    assert "openvino_ir_frontend.dll" in script
    assert "nvinfer*.dll" in script
    assert "opencv*.dll" in script
    assert "opencv_java" in script
    for token in ["PyInstaller", "requirements-worker.txt", "cvds_detector_worker.exe", "conda", "torch", "ultralytics"]:
        assert token.lower() not in script.lower()


def test_cpp_detector_readmes_document_native_openvino_ir_only():
    combined = read_text(CPP_APP / "README.md") + read_text(CPP_APP / "README_RELEASE.md")
    assert "纯 C++ OpenVINO Runtime" in combined
    assert "TensorRT" in combined
    assert ".engine" in combined
    assert ".xml + .bin" in combined
    assert "AUTO / CPU / GPU / NPU" in combined
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
