#pragma once

#include <opencv2/core.hpp>
#include <onnxruntime_cxx_api.h>

#include <memory>
#include <string>
#include <vector>

struct Detection {
    int classId = 0;
    float confidence = 0.0f;
    cv::Rect box;
};

enum class DeviceMode {
    Gpu,
    Cpu
};

class Detector {
public:
    Detector();

    void load(
        const std::wstring& modelPath,
        int inputSize,
        float confidenceThreshold,
        float iouThreshold,
        std::vector<std::string> labels,
        DeviceMode deviceMode,
        int classFilterId
    );

    bool isLoaded() const;
    const std::vector<std::string>& labels() const;
    const std::string& providerName() const;
    static std::string diagnoseGpuEnvironment();
    std::vector<Detection> infer(const cv::Mat& bgrImage);
    cv::Mat drawDetections(const cv::Mat& bgrImage, const std::vector<Detection>& detections) const;

private:
    struct LetterboxResult {
        cv::Mat blob;
        float scale = 1.0f;
        float padX = 0.0f;
        float padY = 0.0f;
    };

    LetterboxResult letterbox(const cv::Mat& bgrImage) const;
    std::vector<Detection> decodeOutput(
        const float* data,
        const std::vector<int64_t>& shape,
        const cv::Size& originalSize,
        const LetterboxResult& letterboxResult
    ) const;
    std::vector<Detection> decodeEndToEndOutput(
        const float* data,
        int64_t boxesCount,
        const cv::Size& originalSize,
        const LetterboxResult& letterboxResult
    ) const;

    Ort::Env env_;
    Ort::SessionOptions sessionOptions_;
    std::unique_ptr<Ort::Session> session_;
    std::string inputName_;
    std::string outputName_;
    int inputSize_ = 960;
    float confidenceThreshold_ = 0.25f;
    float iouThreshold_ = 0.45f;
    int classFilterId_ = -1;
    std::vector<std::string> labels_;
    std::string providerName_ = "CPUExecutionProvider";
};
