#pragma once

#include "RegionConfig.h"

#include <QByteArray>
#include <QJsonObject>
#include <QMetaType>
#include <QString>
#include <QVector>

// 维护说明：以下结构体描述 WCS 集成配置和运行快照。
// 当前主程序仍是 CVDS_Cpp_Detector，WCS 配置只作为可选上报能力。
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

// 维护说明：这里保留历史后端字段，但当前发布运行端以 OpenVINO/TensorRT 为准。
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

// 维护说明：WCS 使用按行 JSON，便于对端 TCP 服务按换行拆包。
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

Q_DECLARE_METATYPE(CameraRuntimeSnapshot)

QByteArray multiCameraSystemConfigToJson(const MultiCameraSystemConfig& config);
MultiCameraSystemConfig multiCameraSystemConfigFromJson(const QByteArray& jsonBytes);
MultiCameraSystemConfig loadMultiCameraSystemConfig(const QString& path);
void saveMultiCameraSystemConfig(const QString& path, const MultiCameraSystemConfig& config);

QJsonObject cameraRuntimeSnapshotToJson(const CameraRuntimeSnapshot& snapshot);
CameraRuntimeSnapshot cameraRuntimeSnapshotFromJson(const QJsonObject& object);
