#include "pipeline/ResultWriter.h"

#include <QDir>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <opencv2/imgcodecs.hpp>

#include <algorithm>

namespace {

QString csvField(QString value) {
    if (!value.contains(',') && !value.contains('"') && !value.contains('\n') && !value.contains('\r')) {
        return value;
    }
    value.replace("\"", "\"\"");
    return "\"" + value + "\"";
}

}  // namespace

bool ResultWriter::open(const QString& outputDir, double fps, const cv::Size& frameSize, QString* error) {
    outputDir_ = outputDir;
    QDir().mkpath(outputDir_);
    flowCsv_.setFileName(QDir(outputDir_).filePath("flow_events.csv"));
    if (!flowCsv_.open(QIODevice::WriteOnly | QIODevice::Text)) {
        if (error) *error = flowCsv_.errorString();
        return false;
    }
    if (!jamJsonl_.begin(QDir(outputDir_).filePath("jam_signals.jsonl"), error)) {
        flowCsv_.close();
        return false;
    }
    flowCsv_.write("frame,track_id,region_id,region_name,event_type,region_flow_count,x,y,inside_count\n");
    if (frameSize.width > 0 && frameSize.height > 0) {
        const QString videoPath = QDir(outputDir_).filePath("cvds_online_parcel_flow_monitor.mp4");
        videoWriter_.open(videoPath.toStdString(), cv::VideoWriter::fourcc('m', 'p', '4', 'v'), std::max(1.0, fps), frameSize);
        if (!videoWriter_.isOpened()) {
            if (error) *error = "无法创建结果视频：" + videoPath;
            close();
            return false;
        }
    }
    return true;
}

void ResultWriter::writeFrame(const cv::Mat& frame) {
    if (videoWriter_.isOpened() && !frame.empty()) videoWriter_.write(frame);
}

void ResultWriter::writePreview(const cv::Mat& frame) {
    if (!frame.empty()) cv::imwrite(previewPath().toStdString(), frame);
}

void ResultWriter::writeFlowEvents(const QVector<RoiEntryEvent>& events, int frameIndex) {
    if (!flowCsv_.isOpen()) return;
    for (const RoiEntryEvent& event : events) {
        const QString line = QString::number(frameIndex) + "," + QString::number(event.trackId) + ","
            + csvField(event.regionId) + "," + csvField(event.regionName) + ",roi_enter,"
            + QString::number(event.regionFlowCount) + ","
            + QString::number(event.center.x, 'f', 3) + ","
            + QString::number(event.center.y, 'f', 3) + ","
            + QString::number(event.insideCount) + "\n";
        flowCsv_.write(line.toUtf8());
    }
}

bool ResultWriter::writeJamSignal(
    const QString& eventType,
    const RegionRuntimeState& state,
    int frameIndex,
    const QString& reason,
    QString* error) {
    QJsonObject object;
    object.insert("type", "jam");
    object.insert("event_type", eventType);
    object.insert("timestamp_ms", QDateTime::currentMSecsSinceEpoch());
    object.insert("frame", frameIndex);
    object.insert("region_id", state.id);
    object.insert("region_name", state.name);
    object.insert("signal", eventType == "jam_detected" ? "IO_JAM_ON" : "IO_JAM_OFF");
    object.insert("inside_count", state.insideCount);
    object.insert("flow_count", state.flowCount);
    object.insert("jam_count", state.jamCount);
    object.insert("stale_seconds", state.staleSeconds);
    if (!reason.isEmpty()) object.insert("reason", reason);
    return jamJsonl_.append(object, error);
}

bool ResultWriter::writeSummary(
    const QVector<RegionRuntimeState>& states,
    const QString& totalRegionId,
    int totalCount,
    int frameCount,
    QString* error) {
    QJsonObject root;
    root.insert("type", "done");
    root.insert("frames", frameCount);
    root.insert("total_count_region", totalRegionId);
    root.insert("total_count", totalCount);
    root.insert("flow_count", totalCount);
    int jamCount = 0;
    int maxInsideCount = 0;
    const bool totalAll = totalRegionId == QStringLiteral("__all_count_regions__");
    QJsonArray regions;
    for (const RegionRuntimeState& s : states) {
        QJsonObject r;
        r.insert("id", s.id);
        r.insert("name", s.name);
        r.insert("flow_count", s.flowCount);
        r.insert("inside_count", s.insideCount);
        r.insert("jam_count", s.jamCount);
        r.insert("jam_active", s.jamActive);
        r.insert("status", s.status);
        r.insert("stale_seconds", s.jamActive ? s.staleSeconds : 0.0);
        jamCount += s.jamCount;
        if (totalAll || s.id == totalRegionId) maxInsideCount = std::max(maxInsideCount, s.maxInsideCount);
        regions.append(r);
    }
    root.insert("jam_count", jamCount);
    root.insert("global_jam_count", jamCount);
    root.insert("max_inside_count", maxInsideCount);
    root.insert("regions", regions);
    root.insert("output_video", QDir(outputDir_).filePath("cvds_online_parcel_flow_monitor.mp4"));
    root.insert("events_csv", QDir(outputDir_).filePath("flow_events.csv"));
    root.insert("jam_signals", QDir(outputDir_).filePath("jam_signals.jsonl"));
    root.insert("summary_json", QDir(outputDir_).filePath("flow_summary.json"));
    QFile file(QDir(outputDir_).filePath("flow_summary.json"));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        if (error) *error = file.errorString();
        return false;
    }
    const QByteArray bytes = QJsonDocument(root).toJson(QJsonDocument::Indented);
    if (file.write(bytes) != bytes.size()) {
        if (error) *error = file.errorString();
        return false;
    }
    return true;
}

void ResultWriter::close() {
    if (videoWriter_.isOpened()) videoWriter_.release();
    if (flowCsv_.isOpen()) flowCsv_.close();
    jamJsonl_.end();
}

QString ResultWriter::previewPath() const {
    return QDir(outputDir_).filePath("cvds_preview.jpg");
}
