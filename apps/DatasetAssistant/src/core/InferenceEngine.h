#pragma once

#include "model/Annotation.h"
#include "model/InferenceConfig.h"

#include <filesystem>
#include <memory>
#include <string>
#include <vector>

struct YoloOutputShape {
    int rows = 0;
    int cols = 0;
};

class InferenceEngine {
public:
    InferenceEngine();
    ~InferenceEngine();
    bool loadModel(const std::filesystem::path& modelPath, const InferenceConfig& config);
    std::vector<DetectionResult> infer(const cv::Mat& image);
    std::string providerName() const;
    GpuDiagnostic diagnoseGpu() const;
    static std::vector<DetectionResult> postprocessYoloOutput(const std::vector<float>& output,
                                                              YoloOutputShape shape,
                                                              int imageWidth,
                                                              int imageHeight,
                                                              const InferenceConfig& config);

private:
    InferenceConfig config_;
    std::string providerName_ = "CPUExecutionProvider";
    bool loaded_ = false;
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
