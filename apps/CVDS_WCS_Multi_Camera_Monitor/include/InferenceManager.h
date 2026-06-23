#pragma once

#include "CameraConfig.h"
#include "FlowEvent.h"
#include "JamEvent.h"
#include "pipeline/VideoPipeline.h"

#include <QHash>
#include <QImage>
#include <QObject>
#include <QThread>

struct InferenceRuntimeConfig {
    QString outputRoot;
    int previewFps = 10;
    int classFilterId = -1;
};

class InferenceManager : public QObject {
    Q_OBJECT

public:
    explicit InferenceManager(QObject* parent = nullptr);
    ~InferenceManager() override;

    void configure(const MultiCameraSystemConfig& systemConfig, const InferenceRuntimeConfig& runtimeConfig);
    bool isRunning() const;

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
    void allFinished();

private slots:
    void handlePipelineFinished(const QString& cameraId);

private:
    struct PipelineState {
        QThread* thread = nullptr;
        VideoPipeline* pipeline = nullptr;
    };

    void startCamera(const CameraConfig& camera);
    QString resolvePath(const QString& path) const;
    void tearDownState(const QString& cameraId, PipelineState state);

    MultiCameraSystemConfig systemConfig_;
    InferenceRuntimeConfig runtimeConfig_;
    QHash<QString, PipelineState> states_;
    bool running_ = false;
};
