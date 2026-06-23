#include "WcsMessage.h"

#include <QDateTime>
#include <QJsonDocument>

namespace {

QString nowIsoUtc() {
    return QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs);
}

QJsonObject baseMessage(const QString& type, const QString& deviceId) {
    QJsonObject object;
    object.insert("msg_type", type);
    object.insert("device_id", deviceId);
    object.insert("timestamp", nowIsoUtc());
    return object;
}

void addCameraIdentity(QJsonObject* object, const QString& cameraId, const QString& lineId, const QString& beltId) {
    object->insert("camera_id", cameraId);
    object->insert("line_id", lineId);
    object->insert("belt_id", beltId);
}

}  // namespace

QJsonObject buildWcsHeartbeatMessage(
    const QString& deviceId,
    int cameraOnline,
    int cameraTotal,
    double gpuUsagePercent
) {
    QJsonObject object = baseMessage("HEARTBEAT", deviceId);
    object.insert("camera_online", cameraOnline);
    object.insert("camera_total", cameraTotal);
    object.insert("gpu_usage", gpuUsagePercent);
    return object;
}

QJsonObject buildWcsCameraStatusMessage(
    const QString& deviceId,
    const CameraRuntimeSnapshot& snapshot
) {
    QJsonObject object = baseMessage("CAMERA_STATUS", deviceId);
    addCameraIdentity(&object, snapshot.cameraId, snapshot.lineId, snapshot.beltId);
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

QJsonObject buildWcsFlowUpdateMessage(
    const QString& deviceId,
    const WcsFlowUpdate& update
) {
    QJsonObject object = baseMessage("FLOW_UPDATE", deviceId);
    addCameraIdentity(&object, update.cameraId, update.lineId, update.beltId);
    object.insert("roi_id", update.roiId);
    object.insert("roi_name", update.roiName);
    object.insert("count_total", update.totalCount);
    object.insert("count_last_minute", update.countLastMinute);
    object.insert("inside_count", update.insideCount);
    object.insert("fps", update.fps);
    return object;
}

QJsonObject buildWcsJamOnMessage(
    const QString& deviceId,
    const WcsJamEvent& event
) {
    QJsonObject object = baseMessage("JAM_ON", deviceId);
    addCameraIdentity(&object, event.cameraId, event.lineId, event.beltId);
    object.insert("roi_id", event.roiId);
    object.insert("roi_name", event.roiName);
    object.insert("jam_confidence", event.jamConfidence);
    object.insert("object_count", event.objectCount);
    object.insert("avg_speed", event.avgSpeed);
    object.insert("stay_time_max", event.maxStaySeconds);
    object.insert("flow_count_window", event.flowCountInWindow);
    object.insert("snapshot", event.snapshotPath);
    return object;
}

QJsonObject buildWcsJamOffMessage(
    const QString& deviceId,
    const WcsJamEvent& event
) {
    QJsonObject object = baseMessage("JAM_OFF", deviceId);
    addCameraIdentity(&object, event.cameraId, event.lineId, event.beltId);
    object.insert("roi_id", event.roiId);
    object.insert("roi_name", event.roiName);
    object.insert("duration_seconds", event.durationSeconds);
    object.insert("snapshot", event.snapshotPath);
    return object;
}

QJsonObject buildWcsErrorMessage(
    const QString& deviceId,
    const QString& cameraId,
    const QString& code,
    const QString& message
) {
    QJsonObject object = baseMessage("ERROR", deviceId);
    object.insert("camera_id", cameraId);
    object.insert("code", code);
    object.insert("message", message);
    return object;
}

QByteArray encodeWcsMessage(const QJsonObject& object, bool newlineDelimitedJson) {
    QByteArray payload = QJsonDocument(object).toJson(QJsonDocument::Compact);
    if (newlineDelimitedJson) {
        payload.append('\n');
    }
    return payload;
}
