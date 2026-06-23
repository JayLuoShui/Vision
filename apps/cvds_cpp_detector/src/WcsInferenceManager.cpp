#include "WcsInferenceManager.h"

#include "RegionConfig.h"
#include "RuntimePaths.h"

#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QProcess>

#include <algorithm>

struct WcsInferenceManager::CameraProcessState {
    CameraConfig camera;
    QProcess* process = nullptr;
    QByteArray buffer;
    CameraRuntimeSnapshot snapshot;
    QString outputDir;
    QString previewPath;
    QHash<QString, int> lastFlowCountByRegion;
    QElapsedTimer fpsTimer;
    int previewFrames = 0;
};

WcsInferenceManager::WcsInferenceManager(QObject* parent)
    : QObject(parent) {}

WcsInferenceManager::~WcsInferenceManager() {
    stop();
}

void WcsInferenceManager::configure(
    const MultiCameraSystemConfig& systemConfig,
    const WcsInferenceRuntimeConfig& runtimeConfig
) {
    if (running_) {
        stop();
    }
    systemConfig_ = systemConfig;
    runtimeConfig_ = runtimeConfig;
}

bool WcsInferenceManager::isRunning() const {
    return running_;
}

void WcsInferenceManager::start() {
    if (running_) {
        return;
    }
    if (systemConfig_.cameras.isEmpty()) {
        emit log("WCS 推理启动失败：未配置摄像头。");
        return;
    }
    const QString workerPath = resolvePath(runtimeConfig_.workerPath);
    if (!QFileInfo::exists(workerPath)) {
        emit log("WCS 推理启动失败：缺少 worker。" + workerPath);
        return;
    }
    const QString modelPath = resolvePath(systemConfig_.inference.modelPath);
    if (!QFileInfo::exists(modelPath)) {
        emit log("WCS 推理启动失败：模型不存在。" + modelPath);
        return;
    }
    const QString trackerPath = resolvePath(systemConfig_.inference.trackerPath);
    if (!trackerPath.trimmed().isEmpty() && !QFileInfo::exists(trackerPath)) {
        emit log("WCS 推理启动失败：tracker 配置不存在。" + trackerPath);
        return;
    }

    QDir().mkpath(runtimeConfig_.outputRoot);
    running_ = true;
    for (const CameraConfig& camera : systemConfig_.cameras) {
        if (!camera.enabled) {
            continue;
        }
        startCamera(camera);
    }
    if (states_.isEmpty()) {
        running_ = false;
        emit log("WCS 推理启动失败：没有启用的摄像头。");
        return;
    }
    emit log(QString("WCS 多路推理已启动：%1 路摄像头。" ).arg(states_.size()));
}

void WcsInferenceManager::stop() {
    running_ = false;
    const QList<CameraProcessState*> states = states_.values();
    for (CameraProcessState* state : states) {
        if (state == nullptr || state->process == nullptr) {
            continue;
        }
        state->process->disconnect(this);
        if (state->process->state() != QProcess::NotRunning) {
            state->process->kill();
            state->process->waitForFinished(3000);
        }
        state->snapshot.status = "OFFLINE";
        emitSnapshot(state);
        state->process->deleteLater();
        delete state;
    }
    states_.clear();
    emit allFinished();
}

void WcsInferenceManager::startCamera(const CameraConfig& camera) {
    if (camera.source.trimmed().isEmpty() || camera.regions.isEmpty()) {
        emit failed(camera.cameraId, "摄像头缺少 source 或 regions 配置。");
        return;
    }

    const QString cameraOutputDir = QDir(runtimeConfig_.outputRoot).filePath(camera.cameraId);
    QDir().mkpath(cameraOutputDir);
    const QString previewPath = QDir(cameraOutputDir).filePath("preview.jpg");
    const QString regionsPath = writeRegionsForCamera(camera, cameraOutputDir);
    const QString jamSignalPath = QDir(cameraOutputDir).filePath("jam_signals.jsonl");

    auto* state = new CameraProcessState();
    state->camera = camera;
    state->outputDir = cameraOutputDir;
    state->previewPath = previewPath;
    state->snapshot.cameraId = camera.cameraId;
    state->snapshot.lineId = camera.lineId;
    state->snapshot.beltId = camera.beltId;
    state->snapshot.status = "STARTING";
    state->fpsTimer.start();

    auto* process = new QProcess(this);
    process->setProcessChannelMode(QProcess::MergedChannels);
    state->process = process;
    states_.insert(camera.cameraId, state);

    QStringList args = {
        "detect",
        "--model", resolvePath(systemConfig_.inference.modelPath),
        "--source", camera.source,
        "--rtsp-transport", camera.rtspTransport,
        "--output-dir", cameraOutputDir,
        "--preview-path", previewPath,
        "--regions", regionsPath,
        "--conf", QString::number(systemConfig_.inference.confidence, 'f', 3),
        "--iou", QString::number(systemConfig_.inference.iou, 'f', 3),
        "--imgsz", QString::number(systemConfig_.inference.inputSize),
        "--device", systemConfig_.inference.device,
        "--class-id", QString::number(runtimeConfig_.classFilterId),
        "--preview-fps", QString::number(std::max(1, runtimeConfig_.previewFps)),
        "--jam-signal-path", jamSignalPath,
        "--tracker", resolvePath(systemConfig_.inference.trackerPath),
    };

    connect(process, &QProcess::readyReadStandardOutput, this, [this, state]() {
        consumeProcessOutput(state);
    });
    connect(process, &QProcess::finished, this, [this, state](int exitCode, QProcess::ExitStatus exitStatus) {
        consumeProcessOutput(state);
        state->snapshot.status = exitCode == 0 && exitStatus == QProcess::NormalExit ? "DONE" : "ERROR";
        if (state->snapshot.status == "ERROR" && state->snapshot.error.isEmpty()) {
            state->snapshot.error = "检测进程异常退出";
        }
        emitSnapshot(state);
        emit log(QString("[%1] 检测进程结束，exitCode=%2。" ).arg(state->camera.cameraId).arg(exitCode));
        states_.remove(state->camera.cameraId);
        state->process->deleteLater();
        delete state;
        if (running_ && states_.isEmpty()) {
            running_ = false;
            emit allFinished();
        }
    });

    emitSnapshot(state);
    process->start(resolvePath(runtimeConfig_.workerPath), args);
    if (!process->waitForStarted(5000)) {
        state->snapshot.status = "ERROR";
        state->snapshot.error = "检测进程启动失败";
        emitSnapshot(state);
        emit failed(camera.cameraId, state->snapshot.error);
        states_.remove(camera.cameraId);
        process->deleteLater();
        delete state;
    }
}

void WcsInferenceManager::consumeProcessOutput(CameraProcessState* state) {
    if (state == nullptr || state->process == nullptr) {
        return;
    }
    state->buffer += state->process->readAllStandardOutput();
    while (true) {
        const int newlineIndex = state->buffer.indexOf('\n');
        if (newlineIndex < 0) {
            break;
        }
        const QByteArray rawLine = state->buffer.left(newlineIndex).trimmed();
        state->buffer.remove(0, newlineIndex + 1);
        if (!rawLine.isEmpty()) {
            handleJsonLine(state, rawLine);
        }
    }
}

void WcsInferenceManager::handleJsonLine(CameraProcessState* state, const QByteArray& rawLine) {
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(rawLine, &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        emit log(QString("[%1] %2").arg(state->camera.cameraId, QString::fromUtf8(rawLine)));
        return;
    }

    const QJsonObject object = document.object();
    const QString type = object.value("type").toString();
    if (type == "status") {
        state->snapshot.status = "RUNNING";
        emitSnapshot(state);
        emit log(QString("[%1] %2").arg(state->camera.cameraId, object.value("message").toString()));
        return;
    }
    if (type == "frame") {
        handleFramePayload(state, object);
        return;
    }
    if (type == "jam") {
        handleJamPayload(state, object);
        return;
    }
    if (type == "error") {
        state->snapshot.status = "ERROR";
        state->snapshot.error = object.value("message").toString();
        emitSnapshot(state);
        emit failed(state->camera.cameraId, state->snapshot.error);
        return;
    }
    if (type == "done") {
        handleFramePayload(state, object);
        emit log(QString("[%1] 检测完成。" ).arg(state->camera.cameraId));
        return;
    }
    emit log(QString("[%1] %2").arg(state->camera.cameraId, QString::fromUtf8(rawLine)));
}

void WcsInferenceManager::handleFramePayload(CameraProcessState* state, const QJsonObject& object) {
    const QString previewPath = object.value("preview_path").toString(state->previewPath);
    if (!previewPath.isEmpty()) {
        const QImage image(previewPath);
        if (!image.isNull()) {
            state->snapshot.frameWidth = image.width();
            state->snapshot.frameHeight = image.height();
            emit frameReady(state->camera.cameraId, image);
        }
    }

    ++state->previewFrames;
    if (state->fpsTimer.elapsed() >= 1000) {
        state->snapshot.inferFps = state->previewFrames * 1000.0 / std::max<qint64>(1, state->fpsTimer.elapsed());
        state->previewFrames = 0;
        state->fpsTimer.restart();
    }

    state->snapshot.status = object.value("global_status").toString("RUNNING");
    state->snapshot.jamActive = object.value("jam_active").toBool(false);
    state->snapshot.totalCount = object.value("total_count").toInt(object.value("flow_count").toInt(state->snapshot.totalCount));
    state->snapshot.insideCount = object.value("inside_count").toInt(state->snapshot.insideCount);

    int jamCount = 0;
    const QJsonArray regions = object.value("regions").toArray();
    for (const QJsonValue& value : regions) {
        if (!value.isObject()) {
            continue;
        }
        const QJsonObject regionObject = value.toObject();
        const QString roiId = regionObject.value("id").toString();
        const QString roiName = regionObject.value("name").toString();
        const int flowCount = regionObject.value("flow_count").toInt();
        const int previousFlowCount = state->lastFlowCountByRegion.value(roiId, flowCount);
        state->lastFlowCountByRegion.insert(roiId, flowCount);
        jamCount += regionObject.value("jam_count").toInt();

        WcsFlowUpdate update;
        update.cameraId = state->camera.cameraId;
        update.lineId = state->camera.lineId;
        update.beltId = state->camera.beltId;
        update.roiId = roiId;
        update.roiName = roiName;
        update.totalCount = flowCount;
        update.countLastMinute = std::max(0, flowCount - previousFlowCount);
        update.insideCount = regionObject.value("inside_count").toInt();
        update.fps = state->snapshot.inferFps;
        emit flowUpdateReady(update);
        emit dashboardPayloadReady(state->camera.cameraId, roiId, regionObject);
    }
    state->snapshot.jamCount = jamCount;
    emitSnapshot(state);
}

void WcsInferenceManager::handleJamPayload(CameraProcessState* state, const QJsonObject& object) {
    const QString eventType = object.value("event_type").toString();
    const QString roiId = object.value("region_id").toString();
    const RegionConfig* region = findRegion(state->camera, roiId);

    WcsJamEvent event;
    event.cameraId = state->camera.cameraId;
    event.lineId = state->camera.lineId;
    event.beltId = state->camera.beltId;
    event.roiId = roiId;
    event.roiName = region == nullptr ? object.value("region_name").toString() : region->name;
    event.snapshotPath = state->previewPath;
    event.jamConfidence = eventType == "jam_detected" ? 1.0 : 0.0;
    event.objectCount = object.value("inside_count").toInt();
    event.flowCountInWindow = object.value("flow_count").toInt();
    event.maxStaySeconds = object.value("stale_seconds").toDouble();
    event.durationSeconds = object.value("stale_seconds").toDouble();

    if (eventType == "jam_detected") {
        state->snapshot.jamActive = true;
        state->snapshot.status = "JAM";
        state->snapshot.jamCount += 1;
        emit jamOnReady(event);
    } else if (eventType == "jam_cleared") {
        state->snapshot.jamActive = false;
        state->snapshot.status = "RUNNING";
        emit jamOffReady(event);
    }
    emitSnapshot(state);
    emit dashboardPayloadReady(state->camera.cameraId, roiId, object);
}

void WcsInferenceManager::emitSnapshot(CameraProcessState* state) {
    if (state != nullptr) {
        emit snapshotReady(state->snapshot);
    }
}

QString WcsInferenceManager::resolvePath(const QString& path) const {
    const QString trimmed = path.trimmed();
    if (trimmed.isEmpty()) {
        return {};
    }
    const QFileInfo info(trimmed);
    if (info.isAbsolute()) {
        return info.absoluteFilePath();
    }
    return QDir(RuntimePaths::appDir()).absoluteFilePath(trimmed);
}

QString WcsInferenceManager::writeRegionsForCamera(const CameraConfig& camera, const QString& cameraOutputDir) const {
    RegionConfigDocument document;
    document.version = 1;
    document.totalCountRegionId = camera.totalCountRegionId.trimmed().isEmpty()
        ? camera.regions.first().id
        : camera.totalCountRegionId.trimmed();
    document.regions = camera.regions;
    const QString regionsPath = QDir(cameraOutputDir).filePath("regions.json");
    saveRegionConfigDocument(regionsPath, document);
    return regionsPath;
}

const RegionConfig* WcsInferenceManager::findRegion(const CameraConfig& camera, const QString& regionId) const {
    for (const RegionConfig& region : camera.regions) {
        if (region.id == regionId) {
            return &region;
        }
    }
    return nullptr;
}
