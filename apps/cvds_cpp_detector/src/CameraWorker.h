#pragma once

#include "WcsConfig.h"

#include <QImage>
#include <QObject>

#include <atomic>

class CameraWorker : public QObject {
    Q_OBJECT

public:
    explicit CameraWorker(CameraConfig config, QObject* parent = nullptr);

public slots:
    void run();
    void stop();

signals:
    void frameReady(const QString& cameraId, const QImage& image);
    void snapshotReady(const CameraRuntimeSnapshot& snapshot);
    void log(const QString& message);
    void failed(const QString& cameraId, const QString& error);
    void finished(const QString& cameraId);

private:
    void emitSnapshot(const QString& status, const QString& error = QString());

    CameraConfig config_;
    std::atomic_bool stopped_ = false;
    CameraRuntimeSnapshot snapshot_;
};
