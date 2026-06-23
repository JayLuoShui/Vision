#include "WcsConfig.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QSaveFile>
#include <QStringList>

#include <cmath>
#include <limits>
#include <stdexcept>

namespace {

std::runtime_error configError(const QString& message) {
    return std::runtime_error(message.toUtf8().constData());
}

QString readString(const QJsonObject& object, const char* key, const QString& defaultValue = {}) {
    const QJsonValue value = object.value(QLatin1String(key));
    return value.isString() ? value.toString().trimmed() : defaultValue;
}

QString requireString(const QJsonObject& object, const char* key, const QString& message) {
    const QString text = readString(object, key);
    if (text.isEmpty()) {
        throw configError(message);
    }
    return text;
}

int readInt(const QJsonObject& object, const char* key, int defaultValue) {
    const QJsonValue value = object.value(QLatin1String(key));
    const double number = value.toDouble(defaultValue);
    if (!value.isDouble() || std::floor(number) != number
        || number < static_cast<double>(std::numeric_limits<int>::min())
        || number > static_cast<double>(std::numeric_limits<int>::max())) {
        return defaultValue;
    }
    return static_cast<int>(number);
}

double readDouble(const QJsonObject& object, const char* key, double defaultValue) {
    const QJsonValue value = object.value(QLatin1String(key));
    return value.isDouble() ? value.toDouble(defaultValue) : defaultValue;
}

bool readBool(const QJsonObject& object, const char* key, bool defaultValue) {
    const QJsonValue value = object.value(QLatin1String(key));
    return value.isBool() ? value.toBool(defaultValue) : defaultValue;
}

QJsonArray polygonToJsonArray(const QVector<QPoint>& polygon) {
    QJsonArray array;
    for (const QPoint& point : polygon) {
        array.push_back(QJsonArray{point.x(), point.y()});
    }
    return array;
}

QVector<QPoint> polygonFromJsonArray(const QJsonArray& array, const QString& ownerId) {
    if (array.size() < 3) {
        throw configError("ROI polygon 至少需要 3 个点：" + ownerId);
    }
    QVector<QPoint> polygon;
    polygon.reserve(array.size());
    for (const QJsonValue& value : array) {
        const QJsonArray point = value.toArray();
        if (point.size() != 2 || !point[0].isDouble() || !point[1].isDouble()) {
            throw configError("ROI polygon 点格式错误：" + ownerId);
        }
        polygon.push_back(QPoint(point[0].toInt(), point[1].toInt()));
    }
    return polygon;
}

QJsonObject regionToJson(const RegionConfig& region) {
    QJsonObject object;
    object.insert("id", region.id);
    object.insert("name", region.name);
    object.insert("polygon", polygonToJsonArray(region.polygon));
    object.insert("count_enabled", region.countEnabled);
    object.insert("jam_enabled", region.jamEnabled);
    object.insert("jam_seconds", region.jamSeconds);
    object.insert("priority", region.priority);
    return object;
}

RegionConfig regionFromJson(const QJsonObject& object, const QString& cameraId) {
    RegionConfig region;
    region.id = requireString(object, "id", "摄像头区域 id 不能为空：" + cameraId);
    region.name = requireString(object, "name", "摄像头区域 name 不能为空：" + cameraId + "/" + region.id);
    const QJsonValue polygonValue = object.value("polygon");
    if (!polygonValue.isArray()) {
        throw configError("摄像头区域缺少 polygon：" + cameraId + "/" + region.id);
    }
    region.polygon = polygonFromJsonArray(polygonValue.toArray(), cameraId + "/" + region.id);
    region.polygonClosed = true;
    region.countEnabled = readBool(object, "count_enabled", true);
    region.jamEnabled = readBool(object, "jam_enabled", true);
    region.jamSeconds = readInt(object, "jam_seconds", 5);
    region.priority = readInt(object, "priority", 0);
    if (region.jamSeconds < 1) {
        throw configError("摄像头区域 jam_seconds 必须大于等于 1：" + cameraId + "/" + region.id);
    }
    return region;
}

QJsonObject cameraToJson(const CameraConfig& camera) {
    QJsonArray regions;
    for (const RegionConfig& region : camera.regions) {
        regions.push_back(regionToJson(region));
    }

    QJsonObject object;
    object.insert("camera_id", camera.cameraId);
    object.insert("name", camera.name);
    object.insert("line_id", camera.lineId);
    object.insert("belt_id", camera.beltId);
    object.insert("source", camera.source);
    object.insert("protocol", camera.protocol);
    object.insert("rtsp_transport", camera.rtspTransport);
    object.insert("vendor", camera.vendor);
    object.insert("username", camera.username);
    object.insert("password", camera.password);
    object.insert("channel", camera.channel);
    object.insert("stream_type", camera.streamType);
    object.insert("enabled", camera.enabled);
    object.insert("target_fps", camera.targetFps);
    object.insert("reconnect_seconds", camera.reconnectSeconds);
    object.insert("inference_stride", camera.inferenceStride);
    object.insert("regions_path", camera.regionsPath);
    object.insert("total_count_region", camera.totalCountRegionId);
    object.insert("regions", regions);
    return object;
}

CameraConfig cameraFromJson(const QJsonObject& object) {
    CameraConfig camera;
    camera.cameraId = requireString(object, "camera_id", "camera_id 不能为空。");
    camera.name = readString(object, "name", camera.cameraId);
    camera.lineId = requireString(object, "line_id", "line_id 不能为空：" + camera.cameraId);
    camera.beltId = requireString(object, "belt_id", "belt_id 不能为空：" + camera.cameraId);
    camera.source = requireString(object, "source", "source 不能为空：" + camera.cameraId);
    camera.protocol = readString(object, "protocol", "rtsp");
    camera.rtspTransport = readString(object, "rtsp_transport", "tcp").toLower();
    camera.vendor = readString(object, "vendor", "generic");
    camera.username = readString(object, "username");
    camera.password = readString(object, "password");
    camera.channel = readInt(object, "channel", 1);
    camera.streamType = readInt(object, "stream_type", 1);
    camera.enabled = readBool(object, "enabled", true);
    camera.targetFps = readInt(object, "target_fps", 12);
    camera.reconnectSeconds = readInt(object, "reconnect_seconds", 5);
    camera.inferenceStride = readInt(object, "inference_stride", 1);
    camera.regionsPath = readString(object, "regions_path");
    camera.totalCountRegionId = readString(object, "total_count_region");

    if (camera.rtspTransport != "tcp" && camera.rtspTransport != "udp") {
        throw configError("rtsp_transport 只支持 tcp 或 udp：" + camera.cameraId);
    }
    if (camera.targetFps < 1) {
        throw configError("target_fps 必须大于等于 1：" + camera.cameraId);
    }
    if (camera.reconnectSeconds < 1) {
        throw configError("reconnect_seconds 必须大于等于 1：" + camera.cameraId);
    }
    if (camera.inferenceStride < 1) {
        throw configError("inference_stride 必须大于等于 1：" + camera.cameraId);
    }

    const QJsonArray regionsArray = object.value("regions").toArray();
    for (const QJsonValue& value : regionsArray) {
        if (!value.isObject()) {
            throw configError("regions 中的元素必须是对象：" + camera.cameraId);
        }
        camera.regions.push_back(regionFromJson(value.toObject(), camera.cameraId));
    }
    if (camera.regions.isEmpty() && camera.regionsPath.isEmpty()) {
        throw configError("摄像头必须内联 regions 或指定 regions_path：" + camera.cameraId);
    }
    if (camera.totalCountRegionId.isEmpty() && !camera.regions.isEmpty()) {
        camera.totalCountRegionId = camera.regions.first().id;
    }
    return camera;
}

QJsonObject inferenceToJson(const GpuInferenceConfig& inference) {
    QJsonObject object;
    object.insert("model_path", inference.modelPath);
    object.insert("backend", inference.backend);
    object.insert("device", inference.device);
    object.insert("input_size", inference.inputSize);
    object.insert("confidence", inference.confidence);
    object.insert("iou", inference.iou);
    object.insert("batch_size", inference.batchSize);
    object.insert("max_queue_size", inference.maxQueueSize);
    object.insert("enable_fp16", inference.enableHalfPrecision);
    object.insert("tracker_path", inference.trackerPath);
    return object;
}

GpuInferenceConfig inferenceFromJson(const QJsonObject& object) {
    GpuInferenceConfig inference;
    inference.modelPath = requireString(object, "model_path", "inference.model_path 不能为空。");
    inference.backend = readString(object, "backend", "tensorrt").toLower();
    inference.device = readString(object, "device", "0");
    inference.inputSize = readInt(object, "input_size", 960);
    inference.confidence = readDouble(object, "confidence", 0.25);
    inference.iou = readDouble(object, "iou", 0.45);
    inference.batchSize = readInt(object, "batch_size", 4);
    inference.maxQueueSize = readInt(object, "max_queue_size", 2);
    inference.enableHalfPrecision = readBool(object, "enable_fp16", true);
    inference.trackerPath = readString(object, "tracker_path");
    if (inference.backend != "tensorrt" && inference.backend != "onnxruntime-gpu" && inference.backend != "pytorch-cuda") {
        throw configError("inference.backend 只支持 tensorrt、onnxruntime-gpu 或 pytorch-cuda。");
    }
    if (inference.inputSize < 320 || inference.batchSize < 1 || inference.maxQueueSize < 1) {
        throw configError("inference 输入尺寸、batch_size 和 max_queue_size 配置非法。");
    }
    return inference;
}

QJsonObject wcsToJson(const WcsEndpointConfig& wcs) {
    QJsonObject object;
    object.insert("enabled", wcs.enabled);
    object.insert("device_id", wcs.deviceId);
    object.insert("host", wcs.host);
    object.insert("port", static_cast<int>(wcs.port));
    object.insert("reconnect_ms", wcs.reconnectMs);
    object.insert("heartbeat_ms", wcs.heartbeatMs);
    object.insert("send_timeout_ms", wcs.sendTimeoutMs);
    object.insert("newline_delimited_json", wcs.newlineDelimitedJson);
    return object;
}

WcsEndpointConfig wcsFromJson(const QJsonObject& object) {
    WcsEndpointConfig wcs;
    wcs.enabled = readBool(object, "enabled", true);
    wcs.deviceId = readString(object, "device_id", "VISION_IPC_01");
    wcs.host = requireString(object, "host", "wcs.host 不能为空。");
    wcs.port = static_cast<quint16>(readInt(object, "port", 9100));
    wcs.reconnectMs = readInt(object, "reconnect_ms", 3000);
    wcs.heartbeatMs = readInt(object, "heartbeat_ms", 1000);
    wcs.sendTimeoutMs = readInt(object, "send_timeout_ms", 500);
    wcs.newlineDelimitedJson = readBool(object, "newline_delimited_json", true);
    if (wcs.port == 0 || wcs.reconnectMs < 100 || wcs.heartbeatMs < 500) {
        throw configError("WCS 端点配置非法。");
    }
    return wcs;
}

void validateSystem(const MultiCameraSystemConfig& config) {
    if (config.version != 1) {
        throw configError("WCS 多摄像头配置仅支持 version=1。");
    }
    if (config.cameras.isEmpty()) {
        throw configError("至少需要配置一路摄像头。");
    }
    QStringList ids;
    for (const CameraConfig& camera : config.cameras) {
        if (ids.contains(camera.cameraId)) {
            throw configError("camera_id 重复：" + camera.cameraId);
        }
        ids.push_back(camera.cameraId);
    }
}

}  // namespace

QByteArray multiCameraSystemConfigToJson(const MultiCameraSystemConfig& config) {
    validateSystem(config);
    QJsonArray cameras;
    for (const CameraConfig& camera : config.cameras) {
        cameras.push_back(cameraToJson(camera));
    }
    QJsonObject root;
    root.insert("version", config.version);
    root.insert("site_id", config.siteId);
    root.insert("inference", inferenceToJson(config.inference));
    root.insert("wcs", wcsToJson(config.wcs));
    root.insert("cameras", cameras);
    return QJsonDocument(root).toJson(QJsonDocument::Indented);
}

MultiCameraSystemConfig multiCameraSystemConfigFromJson(const QByteArray& jsonBytes) {
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(jsonBytes, &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        throw configError("WCS 多摄像头配置 JSON 解析失败：" + parseError.errorString());
    }
    const QJsonObject root = document.object();
    MultiCameraSystemConfig config;
    config.version = readInt(root, "version", 1);
    config.siteId = readString(root, "site_id");
    config.inference = inferenceFromJson(root.value("inference").toObject());
    config.wcs = wcsFromJson(root.value("wcs").toObject());
    const QJsonArray cameras = root.value("cameras").toArray();
    for (const QJsonValue& value : cameras) {
        if (!value.isObject()) {
            throw configError("cameras 中的元素必须是对象。");
        }
        config.cameras.push_back(cameraFromJson(value.toObject()));
    }
    validateSystem(config);
    return config;
}

MultiCameraSystemConfig loadMultiCameraSystemConfig(const QString& path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        throw configError("无法读取 WCS 多摄像头配置文件：" + path);
    }
    return multiCameraSystemConfigFromJson(file.readAll());
}

void saveMultiCameraSystemConfig(const QString& path, const MultiCameraSystemConfig& config) {
    const QFileInfo fileInfo(path);
    if (!QDir().mkpath(fileInfo.absolutePath())) {
        throw configError("无法创建配置目录：" + fileInfo.absolutePath());
    }
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        throw configError("无法写入 WCS 多摄像头配置文件：" + path);
    }
    const QByteArray json = multiCameraSystemConfigToJson(config);
    if (file.write(json) != json.size() || !file.commit()) {
        throw configError("WCS 多摄像头配置写入失败：" + path);
    }
}

QJsonObject cameraRuntimeSnapshotToJson(const CameraRuntimeSnapshot& snapshot) {
    QJsonObject object;
    object.insert("camera_id", snapshot.cameraId);
    object.insert("line_id", snapshot.lineId);
    object.insert("belt_id", snapshot.beltId);
    object.insert("status", snapshot.status);
    object.insert("error", snapshot.error);
    object.insert("decode_fps", snapshot.decodeFps);
    object.insert("infer_fps", snapshot.inferFps);
    object.insert("frame_width", snapshot.frameWidth);
    object.insert("frame_height", snapshot.frameHeight);
    object.insert("dropped_frames", snapshot.droppedFrames);
    object.insert("jam_active", snapshot.jamActive);
    object.insert("total_count", snapshot.totalCount);
    object.insert("inside_count", snapshot.insideCount);
    object.insert("jam_count", snapshot.jamCount);
    return object;
}

CameraRuntimeSnapshot cameraRuntimeSnapshotFromJson(const QJsonObject& object) {
    CameraRuntimeSnapshot snapshot;
    snapshot.cameraId = object.value("camera_id").toString().trimmed();
    snapshot.lineId = object.value("line_id").toString().trimmed();
    snapshot.beltId = object.value("belt_id").toString().trimmed();
    snapshot.status = object.value("status").toString("OFFLINE").trimmed();
    snapshot.error = object.value("error").toString().trimmed();
    snapshot.decodeFps = object.value("decode_fps").toDouble();
    snapshot.inferFps = object.value("infer_fps").toDouble();
    snapshot.frameWidth = object.value("frame_width").toInt();
    snapshot.frameHeight = object.value("frame_height").toInt();
    snapshot.droppedFrames = object.value("dropped_frames").toInt();
    snapshot.jamActive = object.value("jam_active").toBool();
    snapshot.totalCount = object.value("total_count").toInt();
    snapshot.insideCount = object.value("inside_count").toInt();
    snapshot.jamCount = object.value("jam_count").toInt();
    return snapshot;
}
