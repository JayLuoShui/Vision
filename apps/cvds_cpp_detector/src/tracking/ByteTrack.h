#pragma once

#include "DetectionResult.h"
#include "tracking/HungarianMatcher.h"
#include "tracking/Track.h"

#include <vector>

class ByteTrack {
public:
    explicit ByteTrack(
        float matchIou = 0.2f,
        int maxLostFrames = 30,
        float highConfidence = 0.25f,
        float lowConfidence = 0.1f,
        float lowMatchIou = 0.5f,
        float newTrackConfidence = 0.25f);
    DetectionResults update(const DetectionResults& detections, double dtSeconds);
    const std::vector<TrackState>& tracks() const { return tracks_; }

private:
    static float iou(const cv::Rect2f& a, const cv::Rect2f& b);
    std::vector<MatchPair> associate(
        const std::vector<int>& trackIndices,
        const DetectionResults& detections,
        const std::vector<int>& detectionIndices,
        float minimumIou) const;
    void applyMatch(
        TrackState& track,
        const DetectionResult& detection,
        double dtSeconds);

    float matchIou_ = 0.2f;
    float lowMatchIou_ = 0.5f;
    float highConfidence_ = 0.25f;
    float lowConfidence_ = 0.1f;
    float newTrackConfidence_ = 0.25f;
    int maxLostFrames_ = 30;
    int nextId_ = 1;
    std::vector<TrackState> tracks_;
};
