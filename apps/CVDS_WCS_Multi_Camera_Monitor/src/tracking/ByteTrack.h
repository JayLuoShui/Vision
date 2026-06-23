#pragma once

#include "DetectionResult.h"
#include "tracking/Track.h"

#include <vector>

class ByteTrack {
public:
    explicit ByteTrack(float matchIou = 0.3f, int maxLostFrames = 30);
    DetectionResults update(const DetectionResults& detections, double dtSeconds);
    const std::vector<TrackState>& tracks() const { return tracks_; }

private:
    static float iou(const cv::Rect2f& a, const cv::Rect2f& b);

    float matchIou_ = 0.3f;
    int maxLostFrames_ = 30;
    int nextId_ = 1;
    std::vector<TrackState> tracks_;
};
