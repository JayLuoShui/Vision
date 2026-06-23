#include "tracking/Track.h"

DetectionResult detectionFromTrack(const TrackState& track) {
    DetectionResult r;
    r.trackId = track.id;
    r.classId = track.classId;
    r.confidence = track.confidence;
    r.box = track.box;
    return r;
}
