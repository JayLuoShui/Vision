#pragma once
#include "DetectionResult.h"
#include "inference/LetterBox.h"
#include <vector>

struct YoloPostprocessConfig {
    float confidence = 0.25f;
    float iou = 0.45f;
    int classFilterId = -1;
};

DetectionResults parseYoloTensor(const float* data, const std::vector<size_t>& shape, const LetterBoxInfo& meta, const YoloPostprocessConfig& config);
