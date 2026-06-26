#pragma once

#include "RegionConfig.h"
#include "inference/DetectorBackend.h"
#include "pipeline/FlowCounter.h"
#include "pipeline/JamDetector.h"
#include "pipeline/ResultWriter.h"
#include "pipeline/WcsPayloadPublisher.h"
#include "tracking/ByteTrack.h"

#include <QByteArray>
#include <QHash>
#include <QImage>
#include <QObject>
#include <QStringList>

#include <atomic>
#include <memory>

class VideoPipeline : public QObject {
    Q_OBJECT

public:
    struct Config {
        QString modelPath;
        QString sourcePath;
        QString rtspTransport = "tcp";
        QString outputDir;
        RegionConfigDocument regions;
        QVector<QPoint> detectRoi;
        QStringList labels;
        InferenceBackend backend = InferenceBackend::OpenVino;
        int classFilterId = -1;
        int inputSize = 960;
        double confidence = 0.25;
        double iou = 0.45;
        QString device = "AUTO";
        int previewFps = 30;
        double lowSpeedThreshold = 5.0;
        int openTimeoutMs = 8000;
        int readTimeoutMs = 8000;
        bool wcsPayloadJsonlEnabled = false;
        QString wcsPayloadJsonlPath;
    };

    explicit VideoPipeline(Config config, QObject* parent = nullptr);

public slots:
    void start();
    void stop();

signals:
    void frameReady(const QImage& image);
    void dashboardPayloadReady(const QByteArray& payload);
    void log(const QString& message);
    void done(const QString& summary);
    void failed(const QString& error);

private:
    struct PipelineRuntimeContext;

    bool validateConfig(QString* error);
    bool initializeRuntime(PipelineRuntimeContext* context, QString* error);
    bool processCurrentFrame(PipelineRuntimeContext* context);
    void finishRuntime(PipelineRuntimeContext* context);
    void emitSuccess(const PipelineRuntimeContext& context);
    void configurePayloadPublisher();
    bool openCapture(cv::VideoCapture* capture, QString* error) const;
    bool readFrame(cv::VideoCapture* capture, cv::Mat* frame, QString* error) const;
    DetectionResults inferFrame(const cv::Mat& frame, QString* error);
    void configureTracker();
    bool writeAndEmitJamEvents(
        const QHash<QString, QString>& events,
        const QVector<RegionRuntimeState>& states,
        int frameIndex,
        const QString& reason,
        QString* error);
    void emitDonePayload(const QVector<RegionRuntimeState>& states, int frameIndex);
    void emitDashboard(const QJsonObject& payload);
    void emitFramePayload(
        int frameIndex,
        const QImage& image);
    void emitStatsPayload(
        int frameIndex,
        const QVector<RegionRuntimeState>& states,
        int trackedCount);
    void emitJamPayload(
        const QString& eventType,
        const RegionRuntimeState& state,
        int frameIndex,
        const QString& reason = {});
    static QImage matToImage(const cv::Mat& frame);
    cv::Mat drawOverlay(
        const cv::Mat& frame,
        const DetectionResults& tracks,
        const QVector<RegionRuntimeState>& states) const;

    Config config_;
    QVector<RegionConfig> runtimeRegions_;
    std::atomic_bool stopRequested_{false};
    DetectorBackend detector_;
    ByteTrack tracker_;
    FlowCounter flowCounter_;
    JamDetector jamDetector_;
    ResultWriter writer_;
    std::unique_ptr<WcsPayloadPublisher> wcsPublisher_;
};
