cmake_minimum_required(VERSION 3.20)
project(dws_turbojpeg_decoder LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(LIBJPEG_TURBO_ROOT "" CACHE PATH "libjpeg-turbo installation root")
if(NOT LIBJPEG_TURBO_ROOT)
    message(FATAL_ERROR "Set LIBJPEG_TURBO_ROOT to a libjpeg-turbo installation")
endif()

find_path(
    TURBOJPEG_INCLUDE_DIR
    turbojpeg.h
    PATHS "${LIBJPEG_TURBO_ROOT}/include"
    NO_DEFAULT_PATH
    REQUIRED
)
find_library(
    TURBOJPEG_LIBRARY
    NAMES turbojpeg
    PATHS "${LIBJPEG_TURBO_ROOT}/lib"
    NO_DEFAULT_PATH
    REQUIRED
)
find_file(
    TURBOJPEG_DLL
    NAMES turbojpeg.dll
    PATHS "${LIBJPEG_TURBO_ROOT}/bin"
    NO_DEFAULT_PATH
    REQUIRED
)

add_library(dws_turbojpeg_decoder SHARED src/turbojpeg_decoder.cpp)
target_include_directories(dws_turbojpeg_decoder PRIVATE "${TURBOJPEG_INCLUDE_DIR}")
target_link_libraries(dws_turbojpeg_decoder PRIVATE "${TURBOJPEG_LIBRARY}")
target_compile_definitions(dws_turbojpeg_decoder PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
if(MSVC)
    target_compile_options(dws_turbojpeg_decoder PRIVATE /W4 /permissive- /utf-8)
endif()

set(DWS_NATIVE_BIN "${CMAKE_CURRENT_SOURCE_DIR}/bin")
set_target_properties(
    dws_turbojpeg_decoder
    PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${DWS_NATIVE_BIN}"
    RUNTIME_OUTPUT_DIRECTORY_RELEASE "${DWS_NATIVE_BIN}"
)

add_custom_command(
    TARGET dws_turbojpeg_decoder
    POST_BUILD
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${TURBOJPEG_DLL}"
            "${DWS_NATIVE_BIN}/turbojpeg.dll"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
            "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE-libjpeg-turbo.md"
            "${DWS_NATIVE_BIN}/LICENSE-libjpeg-turbo.md"
)
