cmake_minimum_required(VERSION 3.21)

project(CVDSCppDetector LANGUAGES CXX RC)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>DLL")
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_package(OpenCV REQUIRED COMPONENTS core imgproc videoio imgcodecs dnn)
find_package(OpenVINO REQUIRED COMPONENTS Runtime)
find_package(CUDAToolkit QUIET)

option(CVDS_ENABLE_TENSORRT "Build the native TensorRT inference backend when TensorRT SDK is available" ON)

set(PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../..")
set(OPENVINO_RUNTIME_DIR "${OpenVINO_DIR}/../libs")

set(TENSORRT_ROOT "" CACHE PATH "TensorRT SDK root directory")
set(TENSORRT_HINTS
    "${TENSORRT_ROOT}"
    "$ENV{TENSORRT_ROOT}"
    "$ENV{TensorRT_ROOT}"
    "$ENV{TENSORRT_DIR}"
    "$ENV{NV_TENSORRT_ROOT}"
    "C:/TensorRT"
    "C:/Program Files/NVIDIA GPU Computing Toolkit/TensorRT"
)
find_path(TENSORRT_INCLUDE_DIR NvInfer.h
    HINTS ${TENSORRT_HINTS}
    PATH_SUFFIXES include
)
find_library(TENSORRT_NVINFER_LIBRARY
    NAMES nvinfer nvinfer_11 nvinfer_10
    HINTS ${TENSORRT_HINTS}
    PATH_SUFFIXES lib lib/x64 lib64
)
set(CVDS_TENSORRT_AVAILABLE OFF)
if(CVDS_ENABLE_TENSORRT AND TENSORRT_INCLUDE_DIR AND TENSORRT_NVINFER_LIBRARY AND CUDAToolkit_FOUND)
    set(CVDS_TENSORRT_AVAILABLE ON)
endif()

file(GLOB OPENVINO_RUNTIME_DLLS
    "${OPENVINO_RUNTIME_DIR}/openvino*.dll"
    "${OPENVINO_RUNTIME_DIR}/tbb*.dll"
)
list(FILTER OPENVINO_RUNTIME_DLLS INCLUDE REGEX
    "(openvino(_c|_auto_batch_plugin|_auto_plugin|_hetero_plugin|_intel_cpu_plugin|_intel_gpu_plugin|_intel_npu_compiler|_intel_npu_compiler_loader|_intel_npu_plugin|_ir_frontend)?|tbb[^/]*)\\.dll$"
)

file(GLOB OPENCV_RUNTIME_DLLS
    "${OpenCV_DIR}/../bin/opencv*.dll"
    "${OpenCV_DIR}/../../bin/opencv*.dll"
    "${OpenCV_DIR}/x64/vc16/bin/opencv*.dll"
    "${OpenCV_DIR}/x64/vc17/bin/opencv*.dll"
)
list(FILTER OPENCV_RUNTIME_DLLS EXCLUDE REGEX "d\\.dll$")
list(FILTER OPENCV_RUNTIME_DLLS EXCLUDE REGEX "opencv_java.*\\.dll$")

if(CVDS_TENSORRT_AVAILABLE)
    get_filename_component(TENSORRT_LIB_DIR "${TENSORRT_NVINFER_LIBRARY}" DIRECTORY)
    get_filename_component(TENSORRT_ROOT_FROM_LIB "${TENSORRT_LIB_DIR}/.." ABSOLUTE)
    file(GLOB TENSORRT_RUNTIME_DLLS
        "${TENSORRT_ROOT_FROM_LIB}/bin/nvinfer*.dll"
        "${TENSORRT_ROOT_FROM_LIB}/lib/nvinfer*.dll"
        "${TENSORRT_ROOT_FROM_LIB}/lib/x64/nvinfer*.dll"
        "${TENSORRT_ROOT_FROM_LIB}/lib64/nvinfer*.dll"
    )
endif()

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
    src/inference/LetterBox.cpp
    src/inference/LetterBox.h
    src/inference/DetectorBackend.cpp
    src/inference/DetectorBackend.h
    src/inference/OpenVinoDetector.cpp
    src/inference/OpenVinoDetector.h
    src/inference/TensorRtDetector.cpp
    src/inference/TensorRtDetector.h
    src/inference/YoloPostprocess.cpp
    src/inference/YoloPostprocess.h
    src/tracking/ByteTrack.cpp
    src/tracking/ByteTrack.h
    src/tracking/HungarianMatcher.cpp
    src/tracking/HungarianMatcher.h
    src/tracking/KalmanFilter.cpp
    src/tracking/KalmanFilter.h
    src/tracking/Track.cpp
    src/tracking/Track.h
    src/pipeline/FlowCounter.cpp
    src/pipeline/FlowCounter.h
    src/pipeline/JamDetector.cpp
    src/pipeline/JamDetector.h
    src/pipeline/ResultWriter.cpp
    src/pipeline/ResultWriter.h
    src/pipeline/VideoPipeline.cpp
    src/pipeline/VideoPipeline.h
    src/utils/FpsMeter.cpp
    src/utils/FpsMeter.h
    src/utils/Geometry.cpp
    src/utils/Geometry.h
    src/utils/JsonlWriter.cpp
    src/utils/JsonlWriter.h
)

target_include_directories(
    CVDS_Cpp_Detector
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
)

target_link_libraries(
    CVDS_Cpp_Detector
    PRIVATE
        Qt6::Widgets
        openvino::runtime
        ${OpenCV_LIBS}
)

if(CVDS_TENSORRT_AVAILABLE)
    target_compile_definitions(CVDS_Cpp_Detector PRIVATE CVDS_WITH_TENSORRT)
    target_include_directories(CVDS_Cpp_Detector PRIVATE "${TENSORRT_INCLUDE_DIR}")
    target_link_libraries(CVDS_Cpp_Detector PRIVATE "${TENSORRT_NVINFER_LIBRARY}" CUDA::cudart)
    message(STATUS "TensorRT backend enabled: ${TENSORRT_NVINFER_LIBRARY}")
else()
    message(STATUS "TensorRT backend not enabled; set TENSORRT_ROOT and CUDA_PATH to build TensorRT support.")
endif()

add_custom_command(
    TARGET CVDS_Cpp_Detector POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            $<TARGET_RUNTIME_DLLS:CVDS_Cpp_Detector>
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${OPENVINO_RUNTIME_DLLS}
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            ${OPENCV_RUNTIME_DLLS}
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>"
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${PROJECT_ROOT}/VERSION.txt"
            "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>/VERSION.txt"
    COMMAND_EXPAND_LISTS
    COMMENT "复制 CVDS 纯 C++ OpenVINO 运行资源"
)

if(CVDS_TENSORRT_AVAILABLE AND TENSORRT_RUNTIME_DLLS)
    add_custom_command(
        TARGET CVDS_Cpp_Detector POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                ${TENSORRT_RUNTIME_DLLS}
                "$<TARGET_FILE_DIR:CVDS_Cpp_Detector>"
        COMMAND_EXPAND_LISTS
        COMMENT "复制 CVDS TensorRT 运行资源"
    )
endif()

install(TARGETS CVDS_Cpp_Detector RUNTIME DESTINATION .)
install(
    DIRECTORY "${PROJECT_ROOT}/weights"
    DESTINATION models
    FILES_MATCHING
    PATTERN "*.xml"
    PATTERN "*.bin"
)
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/docs" DESTINATION . FILES_MATCHING PATTERN "*.md")
install(FILES "${PROJECT_ROOT}/VERSION.txt" DESTINATION .)
