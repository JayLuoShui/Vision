#include "pipeline/FlowCounter.h"
#include "utils/Geometry.h"

#include <algorithm>

void FlowCounter::configure(const QVector<RegionConfig>& regions, const QString& totalRegionId) {
    regions_ = regions;
    totalRegionId_ = totalRegionId;
    states_.clear();
    pendingEvents_.clear();
    for (const RegionConfig& r : regions_) {
        RoiFlowState s;
        s.id = r.id;
        s.name = r.name;
        states_.insert(r.id, s);
    }
}

QVector<RegionRuntimeState> FlowCounter::update(const DetectionResults& tracks) {
    pendingEvents_.clear();
    QVector<RegionRuntimeState> out;
    for (const RegionConfig& r : regions_) {
        RoiFlowState& s = states_[r.id];
        int inside = 0;
        for (const DetectionResult& det : tracks) {
            if (det.trackId < 0) continue;
            if (!Geometry::pointInPolygon(Geometry::boxCenter(det.box), r.polygon)) continue;
            ++inside;
            if (r.countEnabled && !s.seenTrackIds.value(det.trackId, false)) {
                s.seenTrackIds.insert(det.trackId, true);
                ++s.flowCount;
                RoiEntryEvent event;
                event.trackId = det.trackId;
                event.regionId = r.id;
                event.regionName = r.name;
                event.regionFlowCount = s.flowCount;
                event.center = Geometry::boxCenter(det.box);
                event.insideCount = inside;
                pendingEvents_.push_back(event);
            }
        }
        s.insideCount = inside;
        s.maxInsideCount = std::max(s.maxInsideCount, inside);
        RegionRuntimeState state;
        state.id = r.id;
        state.name = r.name;
        state.status = inside > 0 ? "OCCUPIED" : "IDLE";
        state.flowCount = s.flowCount;
        state.insideCount = s.insideCount;
        state.maxInsideCount = s.maxInsideCount;
        out.push_back(state);
    }
    return out;
}

QVector<RoiEntryEvent> FlowCounter::takeEntryEvents() {
    QVector<RoiEntryEvent> events;
    events.swap(pendingEvents_);
    return events;
}

int FlowCounter::totalCount() const {
    if (!totalRegionId_.isEmpty() && states_.contains(totalRegionId_)) return states_.value(totalRegionId_).flowCount;
    int total = 0;
    for (const RoiFlowState& s : states_) total += s.flowCount;
    return total;
}

int FlowCounter::insideCount() const {
    int total = 0;
    for (const RoiFlowState& s : states_) total += s.insideCount;
    return total;
}
