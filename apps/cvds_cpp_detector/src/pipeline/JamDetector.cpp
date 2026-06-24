#include "pipeline/JamDetector.h"

#include "utils/Geometry.h"

#include <algorithm>

void JamDetector::configure(const QVector<RegionConfig>& regions, double lowSpeedThreshold) {
    regions_ = regions;
    lowSpeedThreshold_ = std::max(0.0, lowSpeedThreshold);
    states_.clear();
    const QDateTime now = QDateTime::currentDateTimeUtc();
    for (const RegionConfig& r : regions_) {
        JamState s;
        s.lastFlowTime = now;
        states_.insert(r.id, s);
    }
}

QVector<RegionRuntimeState> JamDetector::update(
    const QVector<RegionRuntimeState>& flowStates,
    const std::vector<TrackState>& tracks,
    QHash<QString, QString>* events) {
    QVector<RegionRuntimeState> out;
    const QDateTime now = QDateTime::currentDateTimeUtc();
    for (RegionRuntimeState state : flowStates) {
        const auto it = std::find_if(regions_.begin(), regions_.end(), [&](const RegionConfig& r){ return r.id == state.id; });
        if (it == regions_.end() || !it->jamEnabled) {
            out.push_back(state);
            continue;
        }
        JamState& jam = states_[state.id];
        const bool flowChanged = state.flowCount != jam.lastFlowCount;
        const bool becameOccupied = state.insideCount > 0 && !jam.wasOccupied;
        if (flowChanged || becameOccupied) {
            jam.lastFlowCount = state.flowCount;
            jam.lastFlowTime = now;
            jam.staleSeconds = 0.0;
        } else {
            jam.staleSeconds = jam.lastFlowTime.msecsTo(now) / 1000.0;
        }
        bool hasSlowTarget = false;
        for (const TrackState& track : tracks) {
            if (track.missed == 0
                && track.speedPixelsPerSecond <= lowSpeedThreshold_
                && Geometry::pointInPolygon(track.center, it->polygon)) {
                hasSlowTarget = true;
                break;
            }
        }
        const bool shouldJam = state.insideCount > 0
            && hasSlowTarget
            && jam.staleSeconds >= it->jamSeconds;
        if (shouldJam && !jam.active) {
            jam.active = true;
            jam.jamCount += 1;
            if (events) events->insert(state.id, "jam_detected");
        } else if (!shouldJam && jam.active) {
            jam.active = false;
            if (events) events->insert(state.id, "jam_cleared");
        }
        jam.wasOccupied = state.insideCount > 0;
        state.jamActive = jam.active;
        state.jamCount = jam.jamCount;
        state.staleSeconds = jam.staleSeconds;
        state.signal = jam.active ? "IO_JAM_ON" : "IO_JAM_OFF";
        state.eventType = jam.active ? "jam_detected" : "jam_cleared";
        if (jam.active) state.status = "JAM";
        out.push_back(state);
    }
    return out;
}

QVector<RegionRuntimeState> JamDetector::clearActive(
    const QVector<RegionRuntimeState>& flowStates,
    QHash<QString, QString>* events) {
    QVector<RegionRuntimeState> out;
    out.reserve(flowStates.size());
    for (RegionRuntimeState state : flowStates) {
        JamState& jam = states_[state.id];
        if (jam.active) {
            jam.active = false;
            if (events) events->insert(state.id, "jam_cleared");
        }
        state.jamActive = false;
        state.jamCount = jam.jamCount;
        state.staleSeconds = jam.staleSeconds;
        state.signal = "IO_JAM_OFF";
        state.eventType = "jam_cleared";
        if (state.insideCount <= 0) state.status = "IDLE";
        out.push_back(state);
    }
    return out;
}
