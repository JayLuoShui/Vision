#include "pipeline/JamDetector.h"

void JamDetector::configure(const QVector<RegionConfig>& regions) {
    regions_ = regions;
    states_.clear();
    const QDateTime now = QDateTime::currentDateTimeUtc();
    for (const RegionConfig& r : regions_) {
        JamState s;
        s.lastFlowTime = now;
        states_.insert(r.id, s);
    }
}

QVector<RegionRuntimeState> JamDetector::update(const QVector<RegionRuntimeState>& flowStates, const DetectionResults&, QHash<QString, QString>* events) {
    QVector<RegionRuntimeState> out;
    const QDateTime now = QDateTime::currentDateTimeUtc();
    for (RegionRuntimeState state : flowStates) {
        const auto it = std::find_if(regions_.begin(), regions_.end(), [&](const RegionConfig& r){ return r.id == state.id; });
        if (it == regions_.end() || !it->jamEnabled) {
            out.push_back(state);
            continue;
        }
        JamState& jam = states_[state.id];
        if (state.flowCount != jam.lastFlowCount) {
            jam.lastFlowCount = state.flowCount;
            jam.lastFlowTime = now;
            jam.staleSeconds = 0.0;
        } else {
            jam.staleSeconds = jam.lastFlowTime.msecsTo(now) / 1000.0;
        }
        const bool shouldJam = state.insideCount > 0 && jam.staleSeconds >= it->jamSeconds;
        if (shouldJam && !jam.active) {
            jam.active = true;
            jam.jamCount += 1;
            if (events) events->insert(state.id, "jam_detected");
        } else if (!shouldJam && jam.active) {
            jam.active = false;
            if (events) events->insert(state.id, "jam_cleared");
        }
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
