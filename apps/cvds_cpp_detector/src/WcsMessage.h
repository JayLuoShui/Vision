#pragma once

#include "WcsConfig.h"

#include <QByteArray>
#include <QJsonObject>
#include <QString>

struct WcsFlowUpdate {
    QString cameraId;
    QString lineId;
    QString beltId;
    QString roiId;
    QString roiName;
    int totalCount = 0;
    int countLastMinute = 0;
    int insideCount = 0;
    double fps = 0.0;
};

struct WcsJamEvent {
    QString cameraId;
    QString lineId;
    QString beltId;
    QString roiId;
    QString roiName;
    QString snapshotPath;
    double jamConfidence = 0.0;
    double avgSpeed = 0.0;
    double maxStaySeconds = 0.0;
    int objectCount = 0;
    int flowCountInWindow = 0;
    double durationSeconds = 0.0;
};

QJsonObject buildWcsHeartbeatMessage(
    const QString& deviceId,
    int cameraOnline,
    int cameraTotal,
    double gpuUsagePercent
);

QJsonObject buildWcsCameraStatusMessage(
    const QString& deviceId,
    const CameraRuntimeSnapshot& snapshot
);

QJsonObject buildWcsFlowUpdateMessage(
    const QString& deviceId,
    const WcsFlowUpdate& update
);

QJsonObject buildWcsJamOnMessage(
    const QString& deviceId,
    const WcsJamEvent& event
);

QJsonObject buildWcsJamOffMessage(
    const QString& deviceId,
    const WcsJamEvent& event
);

QJsonObject buildWcsErrorMessage(
    const QString& deviceId,
    const QString& cameraId,
    const QString& code,
    const QString& message
);

QByteArray encodeWcsMessage(const QJsonObject& object, bool newlineDelimitedJson = true);
