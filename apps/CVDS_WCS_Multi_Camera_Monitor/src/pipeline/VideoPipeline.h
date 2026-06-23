#pragma once

#include "CameraConfig.h"
#include "FlowEvent.h"
#include "JamEvent.h"
#include "inference/OpenVinoDetector.h"
#include "pipeline/FlowCounter.h"
#include "pipeline/JamDetector.h"
#include "pipeline/ResultWriter.h"
#include "tracking/ByteTrack.h"
#include "utils/FpsMeter.h"

#include <QImage>
#include <QJsonObject>
#include <QObject>

#include <atomic>

class VideoPipeline : public QObject {
    Q_OBJECT

public:
    struct Config {
        CameraConfig camera;
        GpuInferenceConfig inference;
        QString outputDir;
        int previewFps = 10;
        int classFilterId = -1;
    };

    explicit VideoPipeline(Config config, QObject* parent = nullptr);

public slots:
    void start();
    void stop();

signals:
    void frameReady(const QString& cameraId, const QImage& image);
    void snapshotReady(const CameraRuntimeSnapshot& snapshot);
    void flowUpdateReady(const WcsFlowUpdate& update);
    void jamOnReady(const WcsJamEvent& event);
    void jamOffReady(const WcsJamEvent& event);
    void dashboardPayloadReady(const QString& cameraId, const QString& roiId, const QJsonObject& payload);
    void log(const QString& message);
    void failed(const QString& cameraId, const QString& error);
    void finished(const QString& cameraId);

private:
    bool openCapture(cv::VideoCapture* capture, QString* error) const;
    void publishFrame(const cv::Mat& frame);
    void publishStates(const QVector<RegionRuntimeState>& states, double inferFps);
    void emitJamEvent(const QString& eventType, const RegionRuntimeState& state);
    static QImage matToImage(const cv::Mat& frame);
    cv::Mat drawOverlay(const cv::Mat& frame, const DetectionResults& tracks, const QVector<RegionRuntimeState>& states) const;

    Config config_;
    std::atomic_bool stopRequested_{false};
    OpenVinoDetector detector_;
    ByteTrack tracker_;
    FlowCounter flowCounter_;
    JamDetector jamDetector_;
    ResultWriter writer_;
};
