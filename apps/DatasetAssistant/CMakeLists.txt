cmake_minimum_required(VERSION 3.21)

project(DatasetAssistant VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

option(DATASET_ASSISTANT_BUILD_TESTS "Build DatasetAssistant tests" ON)

find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs videoio)

set(ONNXRUNTIME_ROOT "" CACHE PATH "ONNX Runtime root directory")
if(NOT ONNXRUNTIME_ROOT AND DEFINED ENV{ONNXRUNTIME_ROOT})
    set(ONNXRUNTIME_ROOT "$ENV{ONNXRUNTIME_ROOT}")
endif()
if(NOT ONNXRUNTIME_ROOT AND EXISTS "C:/tools/onnxruntime-win-x64-gpu-1.23.2")
    set(ONNXRUNTIME_ROOT "C:/tools/onnxruntime-win-x64-gpu-1.23.2")
elseif(NOT ONNXRUNTIME_ROOT AND EXISTS "C:/tools/onnxruntime-win-x64-1.23.2")
    set(ONNXRUNTIME_ROOT "C:/tools/onnxruntime-win-x64-1.23.2")
endif()

set(CORE_SOURCES
    src/core/AnnotationIO.cpp
    src/core/AnnotationTransform.cpp
    src/core/BatchProcessor.cpp
    src/core/DatasetSplitter.cpp
    src/core/ImageProcessor.cpp
    src/core/InferenceEngine.cpp
    src/core/Logger.cpp
    src/core/ProjectManager.cpp
    src/core/RuntimePaths.cpp
    src/core/TaskScheduler.cpp
    src/core/Tracker.cpp
)

add_library(DatasetAssistantCore STATIC ${CORE_SOURCES})
target_include_directories(DatasetAssistantCore PUBLIC src)
target_link_libraries(DatasetAssistantCore PUBLIC ${OpenCV_LIBS})
if(MSVC)
    target_compile_options(DatasetAssistantCore PUBLIC /utf-8)
endif()
if(ONNXRUNTIME_ROOT)
    target_compile_definitions(DatasetAssistantCore PUBLIC DATASET_ASSISTANT_HAS_ONNXRUNTIME=1)
    target_include_directories(DatasetAssistantCore PUBLIC "${ONNXRUNTIME_ROOT}/include")
    target_link_directories(DatasetAssistantCore PUBLIC "${ONNXRUNTIME_ROOT}/lib")
    target_link_libraries(DatasetAssistantCore PUBLIC onnxruntime)
    set(DATASET_ASSISTANT_ONNXRUNTIME_DLL "${ONNXRUNTIME_ROOT}/lib/onnxruntime.dll")
else()
    target_compile_definitions(DatasetAssistantCore PUBLIC DATASET_ASSISTANT_HAS_ONNXRUNTIME=0)
endif()

set(APP_SOURCES
    src/app/main.cpp
    src/app/MainWindow.cpp
    src/app/MainWindow.h
    src/app/ProjectPanel.cpp
    src/app/ProjectPanel.h
    src/app/BatchProcessPanel.cpp
    src/app/BatchProcessPanel.h
    src/app/AnnotationPanel.cpp
    src/app/AnnotationPanel.h
    src/app/DatasetSplitPanel.cpp
    src/app/DatasetSplitPanel.h
    src/app/DiagnosticsPanel.cpp
    src/app/DiagnosticsPanel.h
    src/app/InferencePanel.cpp
    src/app/InferencePanel.h
    src/app/TaskProgressPanel.cpp
    src/app/TaskProgressPanel.h
)

add_executable(DatasetAssistant WIN32 ${APP_SOURCES})
target_link_libraries(DatasetAssistant PRIVATE DatasetAssistantCore Qt6::Widgets)
if(MSVC)
    target_compile_options(DatasetAssistant PRIVATE /utf-8)
endif()

add_custom_command(
    TARGET DatasetAssistant POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/VERSION.txt"
            "$<TARGET_FILE_DIR:DatasetAssistant>/VERSION.txt"
    COMMAND ${CMAKE_COMMAND} -E copy_directory
            "${CMAKE_CURRENT_SOURCE_DIR}/docs"
            "$<TARGET_FILE_DIR:DatasetAssistant>/docs"
)
if(DATASET_ASSISTANT_ONNXRUNTIME_DLL AND EXISTS "${DATASET_ASSISTANT_ONNXRUNTIME_DLL}")
    add_custom_command(
        TARGET DatasetAssistant POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${DATASET_ASSISTANT_ONNXRUNTIME_DLL}"
                "$<TARGET_FILE_DIR:DatasetAssistant>/onnxruntime.dll"
    )
endif()

if(DATASET_ASSISTANT_BUILD_TESTS)
    enable_testing()
    foreach(test_name IN ITEMS
        test_annotation_transform
        test_annotation_io
        test_batch_processor
        test_dataset_splitter
        test_inference_engine
        test_no_jam_feature
        test_release_packaging
        test_runtime_paths
    )
        add_executable(${test_name} tests/${test_name}.cpp)
        target_link_libraries(${test_name} PRIVATE DatasetAssistantCore)
        if(MSVC)
            target_compile_options(${test_name} PRIVATE /UNDEBUG)
        else()
            target_compile_options(${test_name} PRIVATE -UNDEBUG)
        endif()
        add_test(NAME ${test_name} COMMAND ${test_name})
    endforeach()

    add_executable(visual_annotation_transform tests/visual_annotation_transform.cpp)
    target_link_libraries(visual_annotation_transform PRIVATE DatasetAssistantCore)
    if(MSVC)
        target_compile_options(visual_annotation_transform PRIVATE /utf-8)
    endif()
endif()

install(TARGETS DatasetAssistant RUNTIME DESTINATION .)
install(DIRECTORY docs DESTINATION .)
install(FILES VERSION.txt README.md DESTINATION .)
