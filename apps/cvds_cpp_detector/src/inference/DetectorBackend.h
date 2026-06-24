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
