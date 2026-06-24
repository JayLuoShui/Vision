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
    float speedPixelsPerSecond = 0.0f;
};

using DetectionResults = std::vector<DetectionResult>;
