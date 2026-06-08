#include "core/Tracker.h"

#include <algorithm>

namespace {
double iou(const BBox& a, const BBox& b) {
    const double x1 = std::max(a.x1, b.x1);
    const double y1 = std::max(a.y1, b.y1);
    const double x2 = std::min(a.x2, b.x2);
    const double y2 = std::min(a.y2, b.y2);
    const double inter = std::max(0.0, x2 - x1) * std::max(0.0, y2 - y1);
    const double areaA = std::max(0.0, a.x2 - a.x1) * std::max(0.0, a.y2 - a.y1);
    const double areaB = std::max(0.0, b.x2 - b.x1) * std::max(0.0, b.y2 - b.y1);
    return inter / std::max(1e-9, areaA + areaB - inter);
}
}  // namespace

std::vector<TrackResult> Tracker::update(const std::vector<DetectionResult>& detections) {
    std::vector<TrackResult> current;
    for (const auto& detection : detections) {
        int bestId = -1;
        double bestIou = 0.0;
        for (const auto& prev : previous_) {
            const double score = iou(prev.detection.box, detection.box);
            if (score > bestIou) {
                bestIou = score;
                bestId = prev.trackId;
            }
        }
        current.push_back({bestIou > 0.3 ? bestId : nextId_++, detection});
    }
    previous_ = current;
    return current;
}
