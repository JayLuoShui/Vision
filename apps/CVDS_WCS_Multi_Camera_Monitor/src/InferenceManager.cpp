#include "InferenceManager.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>

InferenceManager::InferenceManager(QObject* parent) : QObject(parent) {}

InferenceManager::~InferenceManager() {
    stop();
}

void InferenceManager::configure(const MultiCameraSystemConfig& systemConfig, const InferenceRuntimeConfig& runtimeConfig) {
    if (isRunning()) stop();
    systemConfig_ = systemConfig;
    runtimeConfig_ = runtimeConfig;
}

bool InferenceManager::isRunning() const {
    return running_ && !states_.isEmpty();
}

QString InferenceManager::resolvePath(const QString& path) const {
    const QString trimmed = path.trimmed();
    if (trimmed.isEmpty()) return trimmed;
    QFileInfo info(trimmed);
    if (info.isAbsolute()) return info.absoluteFilePath();
    return QDir(QCoreApplication::applicationDirPath()).absoluteFilePath(trimmed);
}

void InferenceManager::start() {
    if (isRunning()) return;
    states_.clear();
    running_ = true;

    const QString modelPath = resolvePath(systemConfig_.inference.modelPath);
    if (modelPath.isEmpty() || !QFileInfo::exists(modelPath)) {
        running_ = false;
        emit failed(QString(), "OpenVINO model path is invalid: " + modelPath);
        emit allFinished();
        return;
    }

    for (const CameraConfig& camera : systemConfig_.cameras) {
        if (camera.enabled) startCamera(camera);
    }

    if (states_.isEmpty()) {
        running_ = false;
        emit failed(QString(), "No enabled camera channel.");
        emit allFinished();
        return;
    }

    emit log(QString("WCS OpenVINO C++ scheduler started, cameras=%1, model=%2").arg(states_.size()).arg(modelPath));
}

void InferenceManager::stop() {
    running_ = false;
    const auto states = states_.values();
    for (const PipelineState& state : states) {
        if (state.pipeline) state.pipeline->stop();
    }
    if (states_.isEmpty()) emit allFinished();
}

void InferenceManager::startCamera(const CameraConfig& camera) {
    if (camera.cameraId.trimmed().isEmpty() || states_.contains(camera.cameraId)) return;

    VideoPipeline::Config pipelineConfig;
    pipelineConfig.camera = camera;
    pipelineConfig.inference = systemConfig_.inference;
    pipelineConfig.inference.modelPath = resolvePath(systemConfig_.inference.modelPath);
    pipelineConfig.inference.device = pipelineConfig.inference.device.trimmed().isEmpty() ? QStringLiteral("AUTO") : pipelineConfig.inference.device.trimmed().toUpper();
    pipelineConfig.outputDir = QDir(runtimeConfig_.outputRoot).absoluteFilePath(camera.cameraId);
    pipelineConfig.previewFps = runtimeConfig_.previewFps;
    pipelineConfig.classFilterId = runtimeConfig_.classFilterId;

    auto* thread = new QThread(this);
    auto* pipeline = new VideoPipeline(pipelineConfig);
    pipeline->moveToThread(thread);

    connect(thread, &QThread::started, pipeline, &VideoPipeline::start);
    connect(pipeline, &VideoPipeline::frameReady, this, &InferenceManager::frameReady);
    connect(pipeline, &VideoPipeline::snapshotReady, this, &InferenceManager::snapshotReady);
    connect(pipeline, &VideoPipeline::flowUpdateReady, this, &InferenceManager::flowUpdateReady);
    connect(pipeline, &VideoPipeline::jamOnReady, this, &InferenceManager::jamOnReady);
    connect(pipeline, &VideoPipeline::jamOffReady, this, &InferenceManager::jamOffReady);
    connect(pipeline, &VideoPipeline::dashboardPayloadReady, this, &InferenceManager::dashboardPayloadReady);
    connect(pipeline, &VideoPipeline::log, this, &InferenceManager::log);
    connect(pipeline, &VideoPipeline::failed, this, &InferenceManager::failed);
    connect(pipeline, &VideoPipeline::finished, this, &InferenceManager::handlePipelineFinished);
    connect(pipeline, &VideoPipeline::finished, pipeline, &QObject::deleteLater);
    connect(pipeline, &VideoPipeline::finished, thread, &QThread::quit);
    connect(thread, &QThread::finished, thread, &QObject::deleteLater);

    PipelineState state;
    state.thread = thread;
    state.pipeline = pipeline;
    states_.insert(camera.cameraId, state);
    thread->start();
    emit log("Started camera pipeline: " + camera.cameraId + " -> " + camera.source);
}

void InferenceManager::handlePipelineFinished(const QString& cameraId) {
    PipelineState state = states_.take(cameraId);
    tearDownState(cameraId, state);
    if (states_.isEmpty()) {
        running_ = false;
        emit allFinished();
    }
}

void InferenceManager::tearDownState(const QString& cameraId, PipelineState state) {
    Q_UNUSED(state);
    if (!cameraId.isEmpty()) emit log("Camera pipeline finished: " + cameraId);
}
