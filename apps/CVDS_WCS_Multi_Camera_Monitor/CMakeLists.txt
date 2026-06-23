cmake_minimum_required(VERSION 3.21)

project(CVDSWcsMultiCameraMonitor LANGUAGES CXX RC)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets Network)
find_package(OpenCV REQUIRED COMPONENTS core imgproc videoio)

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
    include/MainWindow.h
    include/CameraConfig.h
    include/DetectionResult.h
    include/FlowEvent.h
    include/JamEvent.h
    include/WcsMessage.h
    "${CVDS_CPP_DETECTOR_SRC}/resources.qrc"
    "${CVDS_CPP_DETECTOR_SRC}/app_icon.rc"
    "${CVDS_CPP_DETECTOR_SRC}/RegionConfig.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/RegionConfig.h"
    "${CVDS_CPP_DETECTOR_SRC}/RuntimePaths.cpp"
    "${CVDS_CPP_DETECTOR_SRC}/RuntimePaths.h"
)

target_include_directories(
    CVDS_WCS_Multi_Camera_Monitor
    PRIVATE
        "${APP_ROOT}/include"
        "${APP_ROOT}/src"
        "${CVDS_CPP_DETECTOR_SRC}"
)

target_link_libraries(
    CVDS_WCS_Multi_Camera_Monitor
    PRIVATE
        Qt6::Widgets
        Qt6::Network
        ${OpenCV_LIBS}
)

add_custom_command(
    TARGET CVDS_WCS_Multi_Camera_Monitor POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/scripts"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/runtime"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/models"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/scripts/gpu_infer_worker.py"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/scripts/gpu_infer_worker.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CVDS_CPP_DETECTOR_ROOT}/scripts/worker_entry.py"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/scripts/worker_entry.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CVDS_CPP_DETECTOR_ROOT}/scripts/inspect_model_metadata.py"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/scripts/inspect_model_metadata.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CVDS_CPP_DETECTOR_ROOT}/scripts/pt_video_flow_monitor.py"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/scripts/pt_video_flow_monitor.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CVDS_CPP_DETECTOR_ROOT}/configs/bytetrack.yaml"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/bytetrack.yaml"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/configs/cameras.json"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/cameras.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${APP_ROOT}/configs/cameras.json"
            "$<TARGET_FILE_DIR:CVDS_WCS_Multi_Camera_Monitor>/configs/cameras.wcs.example.json"
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
    COMMENT "复制 WCS 多路视觉监测运行资源"
)

install(TARGETS CVDS_WCS_Multi_Camera_Monitor RUNTIME DESTINATION .)
install(DIRECTORY configs DESTINATION . FILES_MATCHING PATTERN "*.json")
install(DIRECTORY scripts DESTINATION . FILES_MATCHING PATTERN "*.py")
install(DIRECTORY models DESTINATION .)
install(FILES "${PROJECT_ROOT}/VERSION.txt" DESTINATION .)
