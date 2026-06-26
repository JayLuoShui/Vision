#pragma once

#include "RegionConfig.h"

#include <QJsonObject>
#include <QString>
#include <QVector>

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
