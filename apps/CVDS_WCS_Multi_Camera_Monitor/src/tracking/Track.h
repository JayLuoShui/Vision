#pragma once

#include "DetectionResult.h"
#include <opencv2/core.hpp>

struct TrackState {
    int id = -1;
    int classId = -1;
    float confidence = 0.0f;
    cv::Rect2f box;
    cv::Point2f center;
    cv::Point2f previousCenter;
    int age = 0;
    int missed = 0;
    float speedPixelsPerSecond = 0.0f;
};

DetectionResult detectionFromTrack(const TrackState& track);
