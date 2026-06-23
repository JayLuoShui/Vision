cmake_minimum_required(VERSION 3.21)

project(CVDSCppDetector LANGUAGES CXX RC)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets Network)
find_package(OpenCV REQUIRED COMPONENTS core imgproc videoio)

set(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../..")

add_executable(
    CVDS_Cpp_Detector
    WIN32
    src/main.cpp
    src/MainWindow.cpp
    src/MainWindow.h
    src/resources.qrc
    src/app_icon.rc
    src/RegionConfig.cpp
    src/RegionConfig.h
    src/RuntimePaths.cpp
    src/RuntimePaths.h
    src/WcsConfig.cpp
    src/WcsConfig.h
    src/WcsMessage.cpp
    src/WcsMessage.h
    src/WcsTcpClient.cpp
    src/WcsTcpClient.h
)

target_link_libraries(
    CVDS_Cpp_Detector
    PRIVATE
        Qt6::Widgets
        Qt6::Network
        ${OpenCV_LIBS}
)

add_custom_command(
    TARGET CVDS_Cpp_Detector POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/scripts"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/configs"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/runtime"
    COMMAND ${CMAKE_COMMAND} -E make_directory "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/docs"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/scripts/worker_entry.py"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/scripts/worker_entry.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/scripts/inspect_model_metadata.py"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/scripts/inspect_model_metadata.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/scripts/pt_video_flow_monitor.py"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/scripts/pt_video_flow_monitor.py"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/configs/bytetrack.yaml"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/configs/bytetrack.yaml"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/configs/regions.example.json"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/configs/regions.example.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/configs/cameras.wcs.example.json"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/configs/cameras.wcs.example.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/configs/wcs.example.json"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/configs/wcs.example.json"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${PROJECT_ROOT}/VERSION.txt"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/VERSION.txt"
    COMMENT "复制 CVDS 运行资源"
)

install(TARGETS CVDS_Cpp_Detector RUNTIME DESTINATION .)
install(
    DIRECTORY scripts
    DESTINATION .
    FILES_MATCHING
    PATTERN "*.py"
    PATTERN "__pycache__" EXCLUDE
)
install(DIRECTORY configs DESTINATION . FILES_MATCHING PATTERN "*.yaml" PATTERN "*.json")
install(
    DIRECTORY "${PROJECT_ROOT}/weights"
    DESTINATION .
    FILES_MATCHING
    PATTERN "*.pt"
    PATTERN "*.onnx"
    PATTERN "*.xml"
    PATTERN "*.bin"
    PATTERN "*.yaml"
    PATTERN "*_openvino_model"
)
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/docs" DESTINATION . FILES_MATCHING PATTERN "*.md")
install(FILES "${PROJECT_ROOT}/VERSION.txt" DESTINATION .)
