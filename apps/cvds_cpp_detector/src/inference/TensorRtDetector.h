#pragma once

#include "DetectionResult.h"
#include "inference/LetterBox.h"
#include "inference/YoloPostprocess.h"

#include <opencv2/core.hpp>

#include <QString>

#include <memory>
#include <string>
#include <vector>

class TensorRtDetector {
public:
    TensorRtDetector();
    ~TensorRtDetector();

    TensorRtDetector(const TensorRtDetector&) = delete;
    TensorRtDetector& operator=(const TensorRtDetector&) = delete;

    bool load(const QString& modelPath, const QString& device, int inputSize, QString* error = nullptr);
    DetectionResults infer(
        const cv::Mat& frame,
        float confidence,
        float iou,
        int classFilterId,
        QString* error = nullptr);
    bool isLoaded() const { return loaded_; }

private:
    DetectionResults parseOutput(
        const float* output,
        const std::vector<size_t>& dims,
        const LetterBoxInfo& meta,
        const YoloPostprocessConfig& config) const;
    void reset();

    struct Impl;
    std::unique_ptr<Impl> impl_;
    QString modelPath_;
    int inputWidth_ = 640;
    int inputHeight_ = 640;
    YoloOutputLayout outputLayout_ = YoloOutputLayout::Auto;
    bool loaded_ = false;
};
