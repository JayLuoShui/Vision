#pragma once

#include "RegionConfig.h"

#include <QFile>
#include <QHash>
#include <QJsonObject>
#include <QString>
#include <opencv2/core.hpp>
#include <opencv2/videoio.hpp>

class ResultWriter {
public:
    bool open(const QString& outputDir, double fps, const cv::Size& frameSize, QString* error = nullptr);
    void writeFrame(const cv::Mat& frame);
    void writePreview(const cv::Mat& frame);
    void writeFlowEvents(const QVector<RegionRuntimeState>& states, double timestampSeconds);
    void writeJamSignal(const QString& eventType, const RegionRuntimeState& state, double timestampSeconds);
    void writeSummary(const QVector<RegionRuntimeState>& states, int totalCount, int frameCount);
    void close();

    QString outputDir() const { return outputDir_; }
    QString previewPath() const;

private:
    QString outputDir_;
    QFile flowCsv_;
    QFile jamJsonl_;
    cv::VideoWriter videoWriter_;
};
