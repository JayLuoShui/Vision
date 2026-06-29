#pragma once

#include "DetectionResult.h"
#include "RegionConfig.h"
#include "tracking/Track.h"

#include <QHash>
#include <QJsonObject>
#include <QString>
#include <QVector>

// 维护说明：RoiFlowState 记录单个 ROI 的累计计数和已计过的 trackId。
// 同一轨迹重复进入同一区域时不能重复计数。
struct RoiFlowState {
    QString id;
    QString name;
    int flowCount = 0;
    int insideCount = 0;
    int maxInsideCount = 0;
    QHash<int, bool> seenTrackIds;
};

// 维护说明：RoiEntryEvent 是写 CSV 的瞬时事件，takeEntryEvents() 后会清空。
struct RoiEntryEvent {
    int trackId = -1;
    QString regionId;
    QString regionName;
    int regionFlowCount = 0;
    cv::Point2f center;
    int insideCount = 0;
};

// 维护说明：FlowCounter 每帧运行，只根据跟踪后的目标中心点更新 ROI 计数。
// 堵包判断不在这里做，交给 JamDetector。
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
