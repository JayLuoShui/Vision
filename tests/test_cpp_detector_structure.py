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
    forbidden = ["worker_entry.py", "pt_video_flow_monitor.py", "gpu_infer_worker.py", "PyInstaller", "PATTERN \"*.pt\"", "PATTERN \"*.onnx\""]
    for token in forbidden:
        assert token not in cmake


def test_cpp_detector_cmake_no_longer_installs_python_worker_or_runtime_pt_onnx():
    cmake = read_text(CPP_APP / "CMakeLists.txt")
    assert "find_package(OpenVINO REQUIRED COMPONENTS Runtime)" in cmake
    assert "openvino::runtime" in cmake
    for token in ["worker_entry.py", "inspect_model_metadata.py", "pt_video_flow_monitor.py", "DIRECTORY scripts", "PATTERN \"*.pt\"", "PATTERN \"*.onnx\""]:
        assert token not in cmake


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
