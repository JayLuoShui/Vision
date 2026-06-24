#include "tracking/ByteTrack.h"

#include "utils/Geometry.h"

#include <algorithm>
#include <cmath>

ByteTrack::ByteTrack(
    float matchIou,
    int maxLostFrames,
    float highConfidence,
    float lowConfidence,
    float lowMatchIou,
    float newTrackConfidence)
    : matchIou_(std::clamp(matchIou, 0.0f, 1.0f)),
      lowMatchIou_(std::clamp(lowMatchIou, 0.0f, 1.0f)),
      highConfidence_(std::clamp(highConfidence, 0.0f, 1.0f)),
      lowConfidence_(std::clamp(lowConfidence, 0.0f, highConfidence_)),
      newTrackConfidence_(std::clamp(newTrackConfidence, highConfidence_, 1.0f)),
      maxLostFrames_(std::max(0, maxLostFrames)) {}

float ByteTrack::iou(const cv::Rect2f& a, const cv::Rect2f& b) {
    const float x1 = std::max(a.x, b.x), y1 = std::max(a.y, b.y);
    const float x2 = std::min(a.x + a.width, b.x + b.width), y2 = std::min(a.y + a.height, b.y + b.height);
    const float inter = std::max(0.0f, x2 - x1) * std::max(0.0f, y2 - y1);
    const float uni = a.area() + b.area() - inter;
    return uni <= 0.0f ? 0.0f : inter / uni;
}

std::vector<MatchPair> ByteTrack::associate(
    const std::vector<int>& trackIndices,
    const DetectionResults& detections,
    const std::vector<int>& detectionIndices,
    float minimumIou) const {
    std::vector<std::vector<float>> scores(
        trackIndices.size(), std::vector<float>(detectionIndices.size(), 0.0f));
    for (size_t row = 0; row < trackIndices.size(); ++row) {
        const TrackState& track = tracks_[trackIndices[row]];
        for (size_t column = 0; column < detectionIndices.size(); ++column) {
            const DetectionResult& detection = detections[detectionIndices[column]];
            if (track.classId >= 0 && detection.classId >= 0 &&
                track.classId != detection.classId) {
                continue;
            }
            scores[row][column] = iou(track.box, detection.box);
        }
    }
    return hungarianMatch(scores, minimumIou);
}

void ByteTrack::applyMatch(
    TrackState& track,
    const DetectionResult& detection,
    double dtSeconds) {
    track.box = track.filter.update(detection.box, dtSeconds);
    track.center = Geometry::boxCenter(track.box);
    track.classId = detection.classId;
    track.className = detection.className;
    track.confidence = detection.confidence;
    track.missed = 0;
    const double dt = std::max(1e-3, dtSeconds);
    track.speedPixelsPerSecond = static_cast<float>(
        Geometry::distance(track.center, track.previousCenter) / dt);
}

DetectionResults ByteTrack::update(const DetectionResults& detections, double dtSeconds) {
    const double dt = std::clamp(dtSeconds, 1e-3, 1.0);
    for (TrackState& track : tracks_) {
        track.previousCenter = track.center;
        track.box = track.filter.predict(dt);
        track.center = Geometry::boxCenter(track.box);
        track.age++;
        track.missed++;
    }

    std::vector<int> highDetections;
    std::vector<int> lowDetections;
    for (size_t index = 0; index < detections.size(); ++index) {
        if (detections[index].confidence >= highConfidence_) {
            highDetections.push_back(static_cast<int>(index));
        } else if (detections[index].confidence >= lowConfidence_) {
            lowDetections.push_back(static_cast<int>(index));
        }
    }

    std::vector<int> activeTracks;
    activeTracks.reserve(tracks_.size());
    for (size_t index = 0; index < tracks_.size(); ++index) {
        activeTracks.push_back(static_cast<int>(index));
    }

    std::vector<bool> matchedTracks(tracks_.size(), false);
    std::vector<bool> matchedHigh(highDetections.size(), false);
    const std::vector<MatchPair> firstMatches =
        associate(activeTracks, detections, highDetections, matchIou_);
    for (const MatchPair& match : firstMatches) {
        const int trackIndex = activeTracks[match.track];
        const int detectionIndex = highDetections[match.detection];
        applyMatch(tracks_[trackIndex], detections[detectionIndex], dt);
        matchedTracks[trackIndex] = true;
        matchedHigh[match.detection] = true;
    }

    std::vector<int> unmatchedTracks;
    for (size_t index = 0; index < tracks_.size(); ++index) {
        const TrackState& track = tracks_[index];
        if (!matchedTracks[index] && track.missed == 1) {
            unmatchedTracks.push_back(static_cast<int>(index));
        }
    }
    const std::vector<MatchPair> secondMatches =
        associate(unmatchedTracks, detections, lowDetections, lowMatchIou_);
    for (const MatchPair& match : secondMatches) {
        const int trackIndex = unmatchedTracks[match.track];
        const int detectionIndex = lowDetections[match.detection];
        applyMatch(tracks_[trackIndex], detections[detectionIndex], dt);
        matchedTracks[trackIndex] = true;
    }

    for (size_t highIndex = 0; highIndex < highDetections.size(); ++highIndex) {
        if (matchedHigh[highIndex]) continue;
        const int index = highDetections[highIndex];
        if (!(detections[index].confidence >= newTrackConfidence_)) continue;
        const DetectionResult& detection = detections[index];
        TrackState track;
        track.id = nextId_++;
        track.classId = detection.classId;
        track.className = detection.className;
        track.confidence = detection.confidence;
        track.box = detection.box;
        track.center = Geometry::boxCenter(track.box);
        track.previousCenter = track.center;
        track.age = 1;
        track.filter.initiate(track.box);
        tracks_.push_back(track);
    }

    tracks_.erase(
        std::remove_if(
            tracks_.begin(),
            tracks_.end(),
            [&](const TrackState& track) {
                return track.missed > maxLostFrames_;
            }),
        tracks_.end());

    DetectionResults output;
    output.reserve(tracks_.size());
    for (const TrackState& track : tracks_) {
        if (track.missed == 0) {
            output.push_back(detectionFromTrack(track));
        }
    }
    return output;
}
