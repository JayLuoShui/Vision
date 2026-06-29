#pragma once

#include "DetectionResult.h"
#include "inference/OpenVinoDetector.h"
#include "inference/TensorRtDetector.h"

#include <opencv2/core.hpp>

#include <QString>

enum class InferenceBackend {
    OpenVino,
    TensorRt
};

// 维护说明：DetectorBackend 是推理后端门面，调用方只关心 load/infer。
// 新增后端时优先在这里收口，不要让 VideoPipeline 直接依赖具体 SDK。
InferenceBackend inferenceBackendFromString(const QString& value);
QString inferenceBackendName(InferenceBackend backend);

class DetectorBackend {
public:
    bool load(
        InferenceBackend backend,
        const QString& modelPath,
        const QString& device,
        int inputSize,
        QString* error = nullptr);
    DetectionResults infer(
        const cv::Mat& frame,
        float confidence,
        float iou,
        int classFilterId,
        QString* error = nullptr);
    bool isLoaded() const;

private:
    InferenceBackend backend_ = InferenceBackend::OpenVino;
    OpenVinoDetector openVino_;
    TensorRtDetector tensorRt_;
};
