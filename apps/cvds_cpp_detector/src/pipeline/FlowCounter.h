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

struct RoiEntryEvent {
    int trackId = -1;
    QString regionId;
    QString regionName;
    int regionFlowCount = 0;
    cv::Point2f center;
    int insideCount = 0;
};

class FlowCounter {
public:
    void configure(const QVector<RegionConfig>& regions, const QString& totalRegionId);
    QVector<RegionRuntimeState> update(const DetectionResults& tracks);
    QVector<RoiEntryEvent> takeEntryEvents();
    int totalCount() const;
    int insideCount() const;

private:
    QVector<RegionConfig> regions_;
    QString totalRegionId_;
    QHash<QString, RoiFlowState> states_;
    QVector<RoiEntryEvent> pendingEvents_;
};
