#include "tracking/ByteTrack.h"
#include "utils/Geometry.h"
#include <algorithm>

ByteTrack::ByteTrack(float matchIou, int maxLostFrames) : matchIou_(matchIou), maxLostFrames_(maxLostFrames) {}

float ByteTrack::iou(const cv::Rect2f& a, const cv::Rect2f& b) {
    const float x1 = std::max(a.x, b.x), y1 = std::max(a.y, b.y);
    const float x2 = std::min(a.x + a.width, b.x + b.width), y2 = std::min(a.y + a.height, b.y + b.height);
    const float inter = std::max(0.0f, x2 - x1) * std::max(0.0f, y2 - y1);
    const float uni = a.area() + b.area() - inter;
    return uni <= 0.0f ? 0.0f : inter / uni;
}

DetectionResults ByteTrack::update(const DetectionResults& detections, double dtSeconds) {
    std::vector<bool> used(detections.size(), false);
    for (TrackState& track : tracks_) {
        int best = -1;
        float bestScore = matchIou_;
        for (size_t i = 0; i < detections.size(); ++i) {
            if (!used[i] && iou(track.box, detections[i].box) > bestScore) {
                bestScore = iou(track.box, detections[i].box);
                best = static_cast<int>(i);
            }
        }
        if (best >= 0) {
            used[best] = true;
            track.previousCenter = track.center;
            track.box = detections[best].box;
            track.center = Geometry::boxCenter(track.box);
            track.classId = detections[best].classId;
            track.confidence = detections[best].confidence;
            track.age++;
            track.missed = 0;
            track.speedPixelsPerSecond = static_cast<float>(Geometry::distance(track.center, track.previousCenter) / std::max(1e-3, dtSeconds));
        } else {
            track.missed++;
        }
    }
    for (size_t i = 0; i < detections.size(); ++i) {
        if (used[i]) continue;
        TrackState t;
        t.id = nextId_++;
        t.classId = detections[i].classId;
        t.confidence = detections[i].confidence;
        t.box = detections[i].box;
        t.center = Geometry::boxCenter(t.box);
        t.previousCenter = t.center;
        tracks_.push_back(t);
    }
    tracks_.erase(std::remove_if(tracks_.begin(), tracks_.end(), [&](const TrackState& t){ return t.missed > maxLostFrames_; }), tracks_.end());
    DetectionResults out;
    for (const TrackState& t : tracks_) if (t.missed == 0) out.push_back(detectionFromTrack(t));
    return out;
}
