#pragma once

#include "DetectionResult.h"
#include "inference/LetterBox.h"
#include "inference/YoloPostprocess.h"

#include <openvino/openvino.hpp>
#include <opencv2/core.hpp>

#include <QString>

// 维护说明：OpenVinoDetector 只加载 OpenVINO IR 或模型目录。
// 模型目录必须能唯一定位 .xml，并且同目录存在同名 .bin。
class OpenVinoDetector {
public:
    bool load(const QString& modelPath, const QString& device, int inputSize, QString* error = nullptr);
    DetectionResults infer(const cv::Mat& frame, float confidence, float iou, int classFilterId, QString* error = nullptr);
    bool isLoaded() const { return loaded_; }

private:
    DetectionResults parseOutput(const ov::Tensor& output, const LetterBoxInfo& meta, const YoloPostprocessConfig& config) const;

    ov::Core core_;
    ov::CompiledModel compiledModel_;
    ov::InferRequest inferRequest_;
    ov::Output<const ov::Node> input_;
    QString modelPath_;
    QString device_ = "AUTO";
    int inputWidth_ = 640;
    int inputHeight_ = 640;
    YoloOutputLayout outputLayout_ = YoloOutputLayout::Auto;
    bool loaded_ = false;
};
