#pragma once

#include "DetectionResult.h"
#include "RegionConfig.h"
#include "tracking/Track.h"

#include <QHash>
#include <QJsonObject>
#include <QString>
#include <QVector>

struct RoiFlowState {
    QString id;
    QString name;
    int flowCount = 0;
    int insideCount = 0;
    int maxInsideCount = 0;
    QHash<int, bool> seenTrackIds;
};

class FlowCounter {
public:
    void configure(const QVector<RegionConfig>& regions, const QString& totalRegionId);
    QVector<RegionRuntimeState> update(const DetectionResults& tracks);
    int totalCount() const;
    int insideCount() const;

private:
    QVector<RegionConfig> regions_;
    QString totalRegionId_;
    QHash<QString, RoiFlowState> states_;
};
