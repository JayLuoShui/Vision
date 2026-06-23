#pragma once
#include "DetectionResult.h"
#include "RegionConfig.h"
#include <QDateTime>
#include <QHash>

struct JamState {
    bool active = false;
    int lastFlowCount = 0;
    QDateTime lastFlowTime;
    int jamCount = 0;
    double staleSeconds = 0.0;
};

class JamDetector {
public:
    void configure(const QVector<RegionConfig>& regions);
    QVector<RegionRuntimeState> update(const QVector<RegionRuntimeState>& flowStates, const DetectionResults& tracks, QHash<QString, QString>* events = nullptr);
private:
    QVector<RegionConfig> regions_;
    QHash<QString, JamState> states_;
};
