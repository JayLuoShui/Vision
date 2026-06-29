#pragma once

#include "pipeline/FlowCounter.h"
#include "RegionConfig.h"
#include "utils/JsonlWriter.h"

#include <QFile>
#include <QJsonObject>
#include <QString>
#include <opencv2/core.hpp>
#include <opencv2/videoio.hpp>

// 维护说明：ResultWriter 统一管理单路输出文件。
// 文件名是对外约定，修改前要同步 README、测试和现场交付说明。
class ResultWriter {
public:
    bool open(const QString& outputDir, double fps, const cv::Size& frameSize, QString* error = nullptr);
    void writeFrame(const cv::Mat& frame);
    void writePreview(const cv::Mat& frame);
    void writeFlowEvents(const QVector<RoiEntryEvent>& events, int frameIndex);
    bool writeJamSignal(
        const QString& eventType,
        const RegionRuntimeState& state,
        int frameIndex,
        const QString& reason = {},
        QString* error = nullptr);
    bool writeSummary(
        const QVector<RegionRuntimeState>& states,
        const QString& totalRegionId,
        int totalCount,
        int frameCount,
        QString* error = nullptr);
    void close();

    QString outputDir() const { return outputDir_; }
    QString previewPath() const;

private:
    QString outputDir_;
    QFile flowCsv_;
    JsonlWriter jamJsonl_;
    cv::VideoWriter videoWriter_;
};
