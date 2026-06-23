#pragma once

#include "WcsConfig.h"
#include "WcsMessage.h"

#include <QHash>
#include <QImage>
#include <QJsonObject>
#include <QObject>
#include <QString>

class QProcess;

struct WcsInferenceRuntimeConfig {
    QString workerPath;
    QString outputRoot;
    int previewFps = 15;
    int classFilterId = -1;
};

class WcsInferenceManager : public QObject {
    Q_OBJECT

public:
    explicit WcsInferenceManager(QObject* parent = nullptr);
    ~WcsInferenceManager() override;

    void configure(const MultiCameraSystemConfig& systemConfig, const WcsInferenceRuntimeConfig& runtimeConfig);
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

private:
    struct CameraProcessState;

    void startCamera(const CameraConfig& camera);
    void consumeProcessOutput(CameraProcessState* state);
    void handleJsonLine(CameraProcessState* state, const QByteArray& rawLine);
    void handleFramePayload(CameraProcessState* state, const QJsonObject& object);
    void handleJamPayload(CameraProcessState* state, const QJsonObject& object);
    void emitSnapshot(CameraProcessState* state);
    QString resolvePath(const QString& path) const;
    QString writeRegionsForCamera(const CameraConfig& camera, const QString& cameraOutputDir) const;
    const RegionConfig* findRegion(const CameraConfig& camera, const QString& regionId) const;

    MultiCameraSystemConfig systemConfig_;
    WcsInferenceRuntimeConfig runtimeConfig_;
    QHash<QString, CameraProcessState*> states_;
    bool running_ = false;
};
