#pragma once
#include "DetectionResult.h"
#include "RegionConfig.h"
#include "tracking/Track.h"
#include <QDateTime>
#include <QHash>

struct JamState {
    bool active = false;
    int lastFlowCount = 0;
    QDateTime lastFlowTime;
    int jamCount = 0;
    double staleSeconds = 0.0;
    bool wasOccupied = false;
};

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
