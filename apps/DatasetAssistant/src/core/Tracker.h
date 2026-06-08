#pragma once

#include "model/Annotation.h"

#include <vector>

struct TrackResult {
    int trackId = -1;
    DetectionResult detection;
};

class Tracker {
public:
    std::vector<TrackResult> update(const std::vector<DetectionResult>& detections);

private:
    int nextId_ = 1;
    std::vector<TrackResult> previous_;
};
