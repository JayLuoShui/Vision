#pragma once
#include "DetectionResult.h"
#include "RegionConfig.h"
#include "tracking/Track.h"
#include <QDateTime>
#include <QHash>

// 维护说明：JamState 是单个 ROI 的堵包记忆。
// lastFlowCount/lastFlowTime 用来判断“有包裹但流量不再增长”的持续时间。
struct JamState {
    bool active = false;
    int lastFlowCount = 0;
    QDateTime lastFlowTime;
    int jamCount = 0;
    double staleSeconds = 0.0;
    bool wasOccupied = false;
};

// 维护说明：JamDetector 只根据区域状态和轨迹速度判断堵包/解除。
// 它不写文件、不改 UI，只通过 events 返回 IO_JAM_ON / IO_JAM_OFF。
class JamDetector {
public:
    void configure(const QVector<RegionConfig>& regions, double lowSpeedThreshold);
    QVector<RegionRuntimeState> update(
        const QVector<RegionRuntimeState>& flowStates,
        const std::vector<TrackState>& tracks,
        QHash<QString, QString>* events = nullptr);
    QVector<RegionRuntimeState> clearActive(const QVector<RegionRuntimeState>& flowStates, QHash<QString, QString>* events = nullptr);
private:
    QVector<RegionConfig> regions_;
    QHash<QString, JamState> states_;
    double lowSpeedThreshold_ = 5.0;
};
