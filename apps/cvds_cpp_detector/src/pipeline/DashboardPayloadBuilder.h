#pragma once

#include "RegionConfig.h"

#include <QJsonObject>
#include <QString>
#include <QVector>

// 维护说明：DashboardPayloadBuilder 统一生成 UI 和可选 WCS 发布用的 JSON。
// 新增字段时优先在这里改，避免各处手写不同格式。
class DashboardPayloadBuilder {
public:
    struct FramePayloadInput {
        int frameIndex = 0;
        QString previewPath;
        QString totalCountRegionId;
        QVector<RegionRuntimeState> states;
        int trackedCount = 0;
    };

    struct JamPayloadInput {
        QString eventType;
        RegionRuntimeState state;
        int frameIndex = 0;
        QString reason;
    };

    struct DonePayloadInput {
        int frameIndex = 0;
        QString totalCountRegionId;
        QVector<RegionRuntimeState> states;
        int totalCount = 0;
        QString outputDir;
    };

    static QJsonObject buildFramePayload(const FramePayloadInput& input);
    static QJsonObject buildJamPayload(const JamPayloadInput& input);
    static QJsonObject buildDonePayload(const DonePayloadInput& input);
};
