#include "pipeline/DashboardPayloadBuilder.h"

#include <QDateTime>
#include <QDir>
#include <QJsonArray>

#include <algorithm>

namespace {

constexpr const char* kOutputVideoName = "cvds_online_parcel_flow_monitor.mp4";
constexpr const char* kFlowEventsName = "flow_events.csv";
constexpr const char* kJamSignalsName = "jam_signals.jsonl";
constexpr const char* kSummaryName = "flow_summary.json";

bool isTotalAllRegions(const QString& totalCountRegionId) {
    return totalCountRegionId == QStringLiteral("__all_count_regions__");
}

QJsonObject regionPayload(const RegionRuntimeState& state) {
    QJsonObject object;
    object.insert("id", state.id);
    object.insert("name", state.name);
    object.insert("flow_count", state.flowCount);
    object.insert("inside_count", state.insideCount);
    object.insert("max_inside_count", state.maxInsideCount);
    object.insert("jam_active", state.jamActive);
    object.insert("jam_count", state.jamCount);
    object.insert("status", state.status);
    object.insert("stale_seconds", state.jamActive ? state.staleSeconds : 0.0);
    return object;
}

const RegionRuntimeState* findState(
    const QVector<RegionRuntimeState>& states,
    const QString& regionId) {
    for (const RegionRuntimeState& state : states) {
        if (state.id == regionId) return &state;
    }
    return nullptr;
}

struct RegionAggregate {
    bool jamActive = false;
    bool occupied = false;
    int totalFlowCount = 0;
    int totalInsideCount = 0;
    int jamCount = 0;
    int maxInsideCount = 0;
    QJsonArray regions;
};

RegionAggregate aggregateRegions(
    const QVector<RegionRuntimeState>& states,
    const QString& totalCountRegionId) {
    RegionAggregate aggregate;
    const bool totalAll = isTotalAllRegions(totalCountRegionId);
    const RegionRuntimeState* total = totalAll ? nullptr : findState(states, totalCountRegionId);

    for (const RegionRuntimeState& state : states) {
        aggregate.jamActive = aggregate.jamActive || state.jamActive;
        aggregate.occupied = aggregate.occupied || state.insideCount > 0;
        aggregate.jamCount += state.jamCount;
        aggregate.regions.append(regionPayload(state));

        if (totalAll) {
            aggregate.totalFlowCount += state.flowCount;
            aggregate.totalInsideCount += state.insideCount;
            aggregate.maxInsideCount = std::max(aggregate.maxInsideCount, state.maxInsideCount);
        }
    }

    if (!totalAll && total != nullptr) {
        aggregate.totalFlowCount = total->flowCount;
        aggregate.totalInsideCount = total->insideCount;
        aggregate.maxInsideCount = total->maxInsideCount;
    }

    return aggregate;
}

}  // namespace

QJsonObject DashboardPayloadBuilder::buildFramePayload(const FramePayloadInput& input) {
    const RegionAggregate aggregate = aggregateRegions(input.states, input.totalCountRegionId);

    QJsonObject payload;
    payload.insert("type", "frame");
    payload.insert("frame", input.frameIndex);
    payload.insert("preview_path", input.previewPath);
    payload.insert("total_count", aggregate.totalFlowCount);
    payload.insert("flow_count", aggregate.totalFlowCount);
    payload.insert("inside_count", aggregate.totalInsideCount);
    payload.insert("tracked_count", input.trackedCount);
    payload.insert("jam_active", aggregate.jamActive);
    payload.insert("global_status", aggregate.jamActive ? "JAM" : (aggregate.occupied ? "RUNNING" : "IDLE"));
    payload.insert("regions", aggregate.regions);
    return payload;
}

QJsonObject DashboardPayloadBuilder::buildJamPayload(const JamPayloadInput& input) {
    QJsonObject payload;
    payload.insert("type", "jam");
    payload.insert("event_type", input.eventType);
    payload.insert("timestamp_ms", QDateTime::currentMSecsSinceEpoch());
    payload.insert("frame", input.frameIndex);
    payload.insert("region_id", input.state.id);
    payload.insert("region_name", input.state.name);
    payload.insert("flow_count", input.state.flowCount);
    payload.insert("inside_count", input.state.insideCount);
    payload.insert("jam_count", input.state.jamCount);
    payload.insert("stale_seconds", input.state.staleSeconds);
    payload.insert("signal", input.eventType == "jam_detected" ? "IO_JAM_ON" : "IO_JAM_OFF");
    if (!input.reason.isEmpty()) payload.insert("reason", input.reason);
    return payload;
}

QJsonObject DashboardPayloadBuilder::buildDonePayload(const DonePayloadInput& input) {
    const RegionAggregate aggregate = aggregateRegions(input.states, input.totalCountRegionId);
    const QDir outputDir(input.outputDir);

    QJsonObject payload;
    payload.insert("type", "done");
    payload.insert("frames", input.frameIndex);
    payload.insert("total_count_region", input.totalCountRegionId);
    payload.insert("total_count", input.totalCount);
    payload.insert("flow_count", input.totalCount);
    payload.insert("jam_count", aggregate.jamCount);
    payload.insert("global_jam_count", aggregate.jamCount);
    payload.insert("max_inside_count", aggregate.maxInsideCount);
    payload.insert("regions", aggregate.regions);
    payload.insert("output_video", outputDir.filePath(kOutputVideoName));
    payload.insert("events_csv", outputDir.filePath(kFlowEventsName));
    payload.insert("jam_signals", outputDir.filePath(kJamSignalsName));
    payload.insert("summary_json", outputDir.filePath(kSummaryName));
    return payload;
}
