#pragma once

#include <opencv2/core.hpp>

#include <QString>
#include <vector>

struct DetectionResult {
    int trackId = -1;
    int classId = -1;
    QString className;
    float confidence = 0.0f;
    cv::Rect2f box;
};

using DetectionResults = std::vector<DetectionResult>;
