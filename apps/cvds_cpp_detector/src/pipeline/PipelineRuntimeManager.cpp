#include "pipeline/PipelineRuntimeManager.h"

#include <QMetaObject>
#include <QThread>

namespace {

void setError(QString* error, const QString& message) {
    if (error) *error = message;
}

}  // namespace

PipelineRuntimeManager::PipelineRuntimeManager(QObject* parent)
    : QObject(parent) {}

PipelineRuntimeManager::~PipelineRuntimeManager() {
    stopAndWait();
}

bool PipelineRuntimeManager::start(const QVector<PipelineStartRequest>& requests, QString* error) {
    if (!runtimes_.isEmpty()) {
        setError(error, QStringLiteral("检测任务仍在运行，不能重复启动。"));
        return false;
    }
    if (requests.isEmpty()) {
        setError(error, QStringLiteral("没有可启动的视频检测任务。"));
        return false;
    }

    for (const PipelineStartRequest& request : requests) {
        if (request.cameraId.trimmed().isEmpty()) {
            stopAndWait();
            setError(error, QStringLiteral("视频检测任务缺少 cameraId。"));
            return false;
        }

        auto* thread = new QThread(this);
        auto* pipeline = new VideoPipeline(request.config);
        pipeline->moveToThread(thread);

        Runtime runtime;
        runtime.cameraId = request.cameraId;
        runtime.thread = thread;
        runtime.pipeline = pipeline;
        runtimes_.push_back(runtime);

        connect(thread, &QThread::started, pipeline, &VideoPipeline::start);
        connect(pipeline, &VideoPipeline::frameReady, this, [this, cameraId = runtime.cameraId](const QImage& image) {
            emit frameReady(cameraId, image);
        });
        connect(pipeline, &VideoPipeline::dashboardPayloadReady, this, [this, cameraId = runtime.cameraId](const QByteArray& payload) {
            emit dashboardPayloadReady(cameraId, payload);
        });
        connect(pipeline, &VideoPipeline::log, this, [this, cameraId = runtime.cameraId](const QString& message) {
            emit log(cameraId, message);
        });
        connect(pipeline, &VideoPipeline::done, this, [this, cameraId = runtime.cameraId](const QString& summary) {
            emit done(cameraId, summary);
        });
        connect(pipeline, &VideoPipeline::failed, this, [this, cameraId = runtime.cameraId](const QString& error) {
            emit failed(cameraId, error);
        });
        connect(pipeline, &VideoPipeline::done, pipeline, &QObject::deleteLater);
        connect(pipeline, &VideoPipeline::failed, pipeline, &QObject::deleteLater);
        connect(pipeline, &VideoPipeline::done, thread, &QThread::quit);
        connect(pipeline, &VideoPipeline::failed, thread, &QThread::quit);
        connect(thread, &QThread::finished, this, [this, thread]() {
            cleanupThread(thread);
        });
    }

    for (const Runtime& runtime : runtimes_) {
        if (runtime.thread != nullptr) runtime.thread->start();
    }
    return true;
}

void PipelineRuntimeManager::stop() {
    for (const Runtime& runtime : runtimes_) {
        if (runtime.pipeline != nullptr) {
            QMetaObject::invokeMethod(runtime.pipeline, "stop", Qt::DirectConnection);
        }
    }
}

void PipelineRuntimeManager::stopAndWait() {
    stop();
    const QVector<Runtime> runtimes = runtimes_;
    for (const Runtime& runtime : runtimes) {
        if (runtime.thread == nullptr) continue;
        runtime.thread->quit();
        runtime.thread->wait();
    }
    runtimes_.clear();
}

bool PipelineRuntimeManager::isRunning() const {
    return !runtimes_.isEmpty();
}

int PipelineRuntimeManager::runningCount() const {
    return runtimes_.size();
}

void PipelineRuntimeManager::cleanupThread(QThread* thread) {
    for (int i = 0; i < runtimes_.size(); ++i) {
        if (runtimes_[i].thread == thread) {
            if (runtimes_[i].thread != nullptr) {
                runtimes_[i].thread->deleteLater();
            }
            runtimes_.removeAt(i);
            break;
        }
    }
    if (runtimes_.isEmpty()) {
        emit allFinished();
    }
}

PipelineRuntimeManager::Runtime* PipelineRuntimeManager::findRuntime(QThread* thread) {
    for (Runtime& runtime : runtimes_) {
        if (runtime.thread == thread) return &runtime;
    }
    return nullptr;
}

const PipelineRuntimeManager::Runtime* PipelineRuntimeManager::findRuntime(QThread* thread) const {
    for (const Runtime& runtime : runtimes_) {
        if (runtime.thread == thread) return &runtime;
    }
    return nullptr;
}
