#include "tracking/Track.h"

DetectionResult detectionFromTrack(const TrackState& track) {
    DetectionResult r;
    r.trackId = track.id;
    r.classId = track.classId;
    r.className = track.className;
    r.confidence = track.confidence;
    r.box = track.box;
    r.speedPixelsPerSecond = track.speedPixelsPerSecond;
    return r;
}
