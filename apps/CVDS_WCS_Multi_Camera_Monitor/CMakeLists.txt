cmake_minimum_required(VERSION 3.21)

project(CVDSWcsMultiCameraMonitor LANGUAGES CXX RC)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets Network)
find_package(OpenCV REQUIRED COMPONENTS core imgproc videoio imgcodecs dnn)
find_package(OpenVINO REQUIRED COMPONENTS Runtime)

set(APP_ROOT "${CMAKE_CURRENT_LIST_DIR}")
set(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../..")
set(CVDS_CPP_DETECTOR_ROOT "${CMAKE_CURRENT_LIST_DIR}/../cvds_cpp_detector")
set(CVDS_CPP_DETECTOR_SRC "${CVDS_CPP_DETECTOR_ROOT}/src")

add_executable(
    CVDS_WCS_Multi_Camera_Monitor
    WIN32
    src/main.cpp
    src/MainWindow.cpp
    src/CameraManager.cpp
    src/CameraWorker.cpp
    src/InferenceManager.cpp
    src/DetectionWorker.cpp
    src/RoiEditor.cpp
    src/FlowCounter.cpp
    src/JamDetector.cpp
    src/WcsClient.cpp
    src/ConfigManager.cpp
    src/Logger.cpp
    src/inference/OpenVinoDetector.cpp
    src/inference/LetterBox.cpp
    src/inference/YoloPostprocess.cpp
    src/tracking/ByteTrack.cpp
    src/tracking/KalmanFilter.cpp
    src/tracking/HungarianMatcher.cpp
    src/tracking/Track.cpp
    src/pipeline/VideoPipeline.cpp
    src/pipeline/FlowCounter.cpp
    src/pipeline/JamDetector.cpp
    src/pipeline/ResultWriter.cpp
    src/utils/Geometry.cpp
    src/utils/JsonlWriter.cpp
    src/utils/FpsMeter.cpp
    include/MainWindow.h
    include/InferenceManager.h
    include/CameraConfig.h
    include/DetectionResult.h
    include/FlowEvent.h
    include/JamEvent.h
    include/WcsMessage.h
    src/pipeline/VideoPipeline.h
    src/pipeline/FlowCounter.h
    src/pipeline/JamDetector.h
    src/pipeline/ResultWriter.h
    src/inference/OpenVinoDetector.h
    src/inference/LetterBox.h
    src/inference/YoloPostprocess.h
    src/tracking/ByteTrack.h
    src/tracking/KalmanFilter.h
    src/tracking/HungarianMatcher.h
    src/tracking/Track.h
    src/utils/Geometry.h
    src/utils/JsonlWriter.h
    src/utils/FpsMeter.h
    "${CVDS_CPP_DETECTOR_SRC}/resources.qrc"
    "${CVDS_CPP_DETECTOR_SRC}/app_icon.rc"
    "${CVDS_CPP_DETECTOR_SRC}/RegionConfig.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/RegionConfig.h"
    "${CVDS_CPP_DETECTOR_SRC}/RuntimePaths.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/RuntimePaths.h"
    "${CVDS_CPP_DETECTOR_SRC}/WcsConfig.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/WcsConfig.h"
    "${CVDS_CPP_DETECTOR_SRC}/WcsMessage.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/WcsMessage.h"
    "${CVDS_CPP_DETECTOR_SRC}/WcsTcpClient.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/WcsTcpClient.h"
)

target_include_directories(
    CVDS_WCS_Multi_Camera_Monitor
    PRIVATE
        "${APP_ROOT}/include"
        "${APP_ROOT}/src"
        "${APP_ROOT}/src/inference"
        "${APP_ROOT}/src/tracking"
        "${APP_ROOT}/src/pipeline"
        "${APP_ROOT}/src/utils"
        "${CVDS_CPP_DETECTOR_SRC}"
)

target_link_libraries(
    CVDS_WCS_Multi_Camera_Monitor
    PRIVATE
        Qt6::Widgets
        Qt6::Network
        openvino::runtime
        ${OpenCV_LIBS}
)

add_custom_command(
    TARGET CVDS_WCS_Multi_Camera_Monitor POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/runtime"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/models"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/configs/cameras.json"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/cameras.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/configs/wcs.json"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/wcs.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/configs/regions.json"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/regions.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/configs/runtime.json"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/runtime.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${PROJECT_ROOT}/VERSION.txt"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/VERSION.txt"
    COMMENT "复制纯 C++ OpenVINO WCS 多路视觉监测运行资源"
)

install(TARGETS CVDS_WCS_Multi_Camera_Monitor RUNTIME DESTINATION .)
install(DIRECTORY configs DESTINATION . FILES_MATCHING PATTERN "*.json")
install(DIRECTORY models DESTINATION . FILES_MATCHING PATTERN "*.xml" PATTERN "*.bin")
install(FILES "${PROJECT_ROOT}/VERSION.txt" DESTINATION .)
