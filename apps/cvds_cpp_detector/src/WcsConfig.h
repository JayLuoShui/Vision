#pragma once

#include "RegionConfig.h"

#include <QByteArray>
#include <QJsonObject>
#include <QString>
#include <QVector>

struct CameraConfig {
    QString cameraId;
    QString name;
    QString lineId;
    QString beltId;
    QString source;
    QString protocol = "rtsp";
    QString rtspTransport = "tcp";
    QString vendor = "generic";
    QString username;
    QString password;
    int channel = 1;
    int streamType = 1;
    bool enabled = true;
    int targetFps = 12;
    int reconnectSeconds = 5;
    int inferenceStride = 1;
    QString regionsPath;
    QString totalCountRegionId;
    QVector<RegionConfig> regions;
};

struct GpuInferenceConfig {
    QString modelPath;
    QString backend = "tensorrt";       // tensorrt | onnxruntime-gpu | pytorch-cuda
    QString device = "0";               // NVIDIA GPU index
    int inputSize = 960;
    double confidence = 0.25;
    double iou = 0.45;
    int batchSize = 4;
    int maxQueueSize = 2;
    bool enableHalfPrecision = true;
    QString trackerPath;
};

struct WcsEndpointConfig {
    bool enabled = true;
    QString deviceId = "VISION_IPC_01";
    QString host = "127.0.0.1";
    quint16 port = 9100;
    int reconnectMs = 3000;
    int heartbeatMs = 1000;
    int sendTimeoutMs = 500;
    bool newlineDelimitedJson = true;
};

struct MultiCameraSystemConfig {
    int version = 1;
    QString siteId;
    GpuInferenceConfig inference;
    WcsEndpointConfig wcs;
    QVector<CameraConfig> cameras;
};

struct CameraRuntimeSnapshot {
    QString cameraId;
    QString lineId;
    QString beltId;
    QString status = "OFFLINE";
    QString error;
    double decodeFps = 0.0;
    double inferFps = 0.0;
    int frameWidth = 0;
    int frameHeight = 0;
    int droppedFrames = 0;
    bool jamActive = false;
    int totalCount = 0;
    int insideCount = 0;
    int jamCount = 0;
};

QByteArray multiCameraSystemConfigToJson(const MultiCameraSystemConfig& config);
MultiCameraSystemConfig multiCameraSystemConfigFromJson(const QByteArray& jsonBytes);
MultiCameraSystemConfig loadMultiCameraSystemConfig(const QString& path);
void saveMultiCameraSystemConfig(const QString& path, const MultiCameraSystemConfig& config);

QJsonObject cameraRuntimeSnapshotToJson(const CameraRuntimeSnapshot& snapshot);
CameraRuntimeSnapshot cameraRuntimeSnapshotFromJson(const QJsonObject& object);
