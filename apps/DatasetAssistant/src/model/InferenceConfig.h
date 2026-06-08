#pragma once

#include <filesystem>
#include <string>
#include <vector>

enum class DevicePolicy {
    Auto,
    Cpu,
    Gpu
};

struct InferenceConfig {
    std::filesystem::path modelPath;
    std::filesystem::path namesPath;
    std::vector<std::string> classNames;
    DevicePolicy devicePolicy = DevicePolicy::Auto;
    int inputWidth = 640;
    int inputHeight = 640;
    float confidenceThreshold = 0.25f;
    float iouThreshold = 0.45f;
};

struct GpuDiagnostic {
    bool cudaProviderAvailable = false;
    bool cpuProviderAvailable = true;
    std::string gpuName;
    std::vector<std::string> errors;
};
