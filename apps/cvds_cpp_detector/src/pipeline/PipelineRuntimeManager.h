#pragma once

#include "pipeline/VideoPipeline.h"

#include <QByteArray>
#include <QImage>
#include <QObject>
#include <QString>
#include <QVector>

class QThread;

// 维护说明：每个请求对应一路相机和一个 VideoPipeline 实例。
struct PipelineStartRequest {
    QString cameraId;
    VideoPipeline::Config config;
};

// 维护说明：PipelineRuntimeManager 只管线程和信号转发，不参与推理、计数或 UI 聚合。
// 这样 MainWindow 不需要直接持有多个 QThread/VideoPipeline 指针。
class PipelineRuntimeManager final : public QObject {
    Q_OBJECT

public:
    explicit PipelineRuntimeManager(QObject* parent = nullptr);
    ~PipelineRuntimeManager() override;

    bool start(const QVector<PipelineStartRequest>& requests, QString* error = nullptr);
    void stop();
    void stopAndWait();
    bool isRunning() const;
    int runningCount() const;

signals:
    void frameReady(const QString& cameraId, const QImage& image);
    void dashboardPayloadReady(const QString& cameraId, const QByteArray& payload);
    void log(const QString& cameraId, const QString& message);
    void done(const QString& cameraId, const QString& summary);
    void failed(const QString& cameraId, const QString& error);
    void allFinished();

private:
    struct Runtime {
        QString cameraId;
        QThread* thread = nullptr;
        VideoPipeline* pipeline = nullptr;
    };

    void cleanupThread(QThread* thread);
    Runtime* findRuntime(QThread* thread);
    const Runtime* findRuntime(QThread* thread) const;

    QVector<Runtime> runtimes_;
};
