#include "pipeline/ResultWriter.h"

#include <QDir>
#include <QJsonArray>
#include <QJsonDocument>
#include <QTextStream>
#include <opencv2/imgcodecs.hpp>

bool ResultWriter::open(const QString& outputDir, double fps, const cv::Size& frameSize, QString* error) {
    outputDir_ = outputDir;
    QDir().mkpath(outputDir_);
    flowCsv_.setFileName(QDir(outputDir_).filePath("flow_events.csv"));
    jamJsonl_.setFileName(QDir(outputDir_).filePath("jam_signals.jsonl"));
    if (!flowCsv_.open(QIODevice::WriteOnly | QIODevice::Text)) {
        if (error) *error = flowCsv_.errorString();
        return false;
    }
    if (!jamJsonl_.open(QIODevice::WriteOnly | QIODevice::Text)) {
        if (error) *error = jamJsonl_.errorString();
        return false;
    }
    flowCsv_.write("timestamp_seconds,region_id,region_name,flow_count,inside_count,jam_active\n");
    if (frameSize.width > 0 && frameSize.height > 0) {
        const QString videoPath = QDir(outputDir_).filePath("cvds_online_parcel_flow_monitor.mp4");
        videoWriter_.open(videoPath.toStdString(), cv::VideoWriter::fourcc('m', 'p', '4', 'v'), std::max(1.0, fps), frameSize);
    }
    return true;
}

void ResultWriter::writeFrame(const cv::Mat& frame) {
    if (videoWriter_.isOpened() && !frame.empty()) videoWriter_.write(frame);
}

void ResultWriter::writePreview(const cv::Mat& frame) {
    if (!frame.empty()) cv::imwrite(previewPath().toStdString(), frame);
}

void ResultWriter::writeFlowEvents(const QVector<RegionRuntimeState>& states, double timestampSeconds) {
    if (!flowCsv_.isOpen()) return;
    for (const RegionRuntimeState& s : states) {
        const QString line = QString::number(timestampSeconds, 'f', 3) + "," + s.id + "," + s.name + "," +
            QString::number(s.flowCount) + "," + QString::number(s.insideCount) + "," + (s.jamActive ? "1" : "0") + "\n";
        flowCsv_.write(line.toUtf8());
    }
}

void ResultWriter::writeJamSignal(const QString& eventType, const RegionRuntimeState& state, double timestampSeconds) {
    if (!jamJsonl_.isOpen()) return;
    QJsonObject object;
    object.insert("timestamp_seconds", timestampSeconds);
    object.insert("event_type", eventType);
    object.insert("region_id", state.id);
    object.insert("region_name", state.name);
    object.insert("signal", eventType == "jam_detected" ? "IO_JAM_ON" : "IO_JAM_OFF");
    object.insert("inside_count", state.insideCount);
    object.insert("flow_count", state.flowCount);
    object.insert("stale_seconds", state.staleSeconds);
    jamJsonl_.write(QJsonDocument(object).toJson(QJsonDocument::Compact));
    jamJsonl_.write("\n");
}

void ResultWriter::writeSummary(const QVector<RegionRuntimeState>& states, int totalCount, int frameCount) {
    QJsonObject root;
    root.insert("total_count", totalCount);
    root.insert("frame_count", frameCount);
    QJsonArray regions;
    for (const RegionRuntimeState& s : states) {
        QJsonObject r;
        r.insert("id", s.id);
        r.insert("name", s.name);
        r.insert("flow_count", s.flowCount);
        r.insert("inside_count", s.insideCount);
        r.insert("jam_count", s.jamCount);
        r.insert("jam_active", s.jamActive);
        regions.append(r);
    }
    root.insert("regions", regions);
    QFile file(QDir(outputDir_).filePath("flow_summary.json"));
    if (file.open(QIODevice::WriteOnly | QIODevice::Text)) file.write(QJsonDocument(root).toJson(QJsonDocument::Indented));
}

void ResultWriter::close() {
    if (videoWriter_.isOpened()) videoWriter_.release();
    if (flowCsv_.isOpen()) flowCsv_.close();
    if (jamJsonl_.isOpen()) jamJsonl_.close();
}

QString ResultWriter::previewPath() const {
    return QDir(outputDir_).filePath("cvds_preview.jpg");
}
