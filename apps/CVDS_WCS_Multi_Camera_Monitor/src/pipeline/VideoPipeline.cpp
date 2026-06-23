#include "pipeline/VideoPipeline.h"

#include "utils/Geometry.h"

#include <QDateTime>
#include <QDir>
#include <QJsonArray>
#include <QThread>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

VideoPipeline::VideoPipeline(Config config, QObject* parent)
    : QObject(parent), config_(std::move(config)), tracker_(0.3f, 30) {}

void VideoPipeline::stop() {
    stopRequested_.storeRelaxed(true);
}

bool VideoPipeline::openCapture(cv::VideoCapture* capture, QString* error) const {
    const QString source = config_.camera.source.trimmed();
    bool ok = false;
    bool numeric = false;
    const int index = source.toInt(&numeric);
    if (numeric) ok = capture->open(index);
    else ok = capture->open(source.toStdString(), cv::CAP_FFMPEG);
    if (!ok && error) *error = "无法打开视频源：" + source;
    return ok;
}

void VideoPipeline::start() {
    stopRequested_.storeRelaxed(false);
    QString error;
    if (!detector_.load(config_.inference.modelPath, config_.inference.device, config_.inference.inputSize, &error)) {
        emit failed(config_.camera.cameraId, error);
        emit finished(config_.camera.cameraId);
        return;
    }

    cv::VideoCapture capture;
    if (!openCapture(&capture, &error)) {
        emit failed(config_.camera.cameraId, error);
        emit finished(config_.camera.cameraId);
        return;
    }

    const double sourceFps = std::max(1.0, capture.get(cv::CAP_PROP_FPS));
    cv::Mat frame;
    if (!capture.read(frame) || frame.empty()) {
        emit failed(config_.camera.cameraId, "视频源无有效首帧");
        emit finished(config_.camera.cameraId);
        return;
    }

    QDir().mkpath(config_.outputDir);
    if (!writer_.open(config_.outputDir, sourceFps, frame.size(), &error)) {
        emit failed(config_.camera.cameraId, error);
        emit finished(config_.camera.cameraId);
        return;
    }

    flowCounter_.configure(config_.camera.regions, config_.camera.totalCountRegionId);
    jamDetector_.configure(config_.camera.regions);
    FpsMeter decodeFps;
    FpsMeter inferFps;
    decodeFps.reset();
    inferFps.reset();
    int frameIndex = 0;
    QVector<RegionRuntimeState> lastStates;

    while (!stopRequested_.loadRelaxed()) {
        if (frame.empty()) {
            if (!capture.read(frame) || frame.empty()) break;
        }
        const double dFps = decodeFps.addFrame();
        QString inferError;
        DetectionResults detections;
        if (frameIndex % std::max(1, config_.camera.inferenceStride) == 0) {
            detections = detector_.infer(frame, static_cast<float>(config_.inference.confidence), static_cast<float>(config_.inference.iou), config_.classFilterId, &inferError);
        }
        if (!inferError.isEmpty()) emit log("[" + config_.camera.cameraId + "] " + inferError);
        DetectionResults tracks = tracker_.update(detections, 1.0 / sourceFps);
        QVector<RegionRuntimeState> flowStates = flowCounter_.update(tracks);
        QHash<QString, QString> jamEvents;
        QVector<RegionRuntimeState> states = jamDetector_.update(flowStates, tracks, &jamEvents);
        lastStates = states;
        const double iFps = inferFps.addFrame();
        cv::Mat overlay = drawOverlay(frame, tracks, states);
        writer_.writeFrame(overlay);
        writer_.writePreview(overlay);
        writer_.writeFlowEvents(states, frameIndex / sourceFps);
        for (auto it = jamEvents.constBegin(); it != jamEvents.constEnd(); ++it) {
            for (const RegionRuntimeState& state : states) {
                if (state.id == it.key()) {
                    writer_.writeJamSignal(it.value(), state, frameIndex / sourceFps);
                    emitJamEvent(it.value(), state);
                }
            }
        }
        publishFrame(overlay);
        publishStates(states, iFps);
        CameraRuntimeSnapshot snapshot;
        snapshot.cameraId = config_.camera.cameraId;
        snapshot.lineId = config_.camera.lineId;
        snapshot.beltId = config_.camera.beltId;
        snapshot.status = "RUNNING";
        snapshot.decodeFps = dFps;
        snapshot.inferFps = iFps;
        snapshot.frameWidth = frame.cols;
        snapshot.frameHeight = frame.rows;
        snapshot.totalCount = flowCounter_.totalCount();
        snapshot.insideCount = flowCounter_.insideCount();
        for (const RegionRuntimeState& state : states) {
            snapshot.jamActive = snapshot.jamActive || state.jamActive;
            snapshot.jamCount += state.jamCount;
        }
        emit snapshotReady(snapshot);
        ++frameIndex;
        frame.release();
        capture.read(frame);
        QThread::msleep(1);
    }

    writer_.writeSummary(lastStates, flowCounter_.totalCount(), frameIndex);
    writer_.close();
    capture.release();
    emit finished(config_.camera.cameraId);
}

void VideoPipeline::publishFrame(const cv::Mat& frame) {
    emit frameReady(config_.camera.cameraId, matToImage(frame));
}

void VideoPipeline::publishStates(const QVector<RegionRuntimeState>& states, double inferFps) {
    for (const RegionRuntimeState& state : states) {
        WcsFlowUpdate update;
        update.cameraId = config_.camera.cameraId;
        update.lineId = config_.camera.lineId;
        update.beltId = config_.camera.beltId;
        update.roiId = state.id;
        update.roiName = state.name;
        update.totalCount = state.flowCount;
        update.insideCount = state.insideCount;
        update.fps = inferFps;
        emit flowUpdateReady(update);
        emit dashboardPayloadReady(config_.camera.cameraId, state.id, regionRuntimeStateToJson(state));
    }
}

void VideoPipeline::emitJamEvent(const QString& eventType, const RegionRuntimeState& state) {
    WcsJamEvent event;
    event.cameraId = config_.camera.cameraId;
    event.lineId = config_.camera.lineId;
    event.beltId = config_.camera.beltId;
    event.roiId = state.id;
    event.roiName = state.name;
    event.snapshotPath = writer_.previewPath();
    event.objectCount = state.insideCount;
    event.flowCountInWindow = state.flowCount;
    event.maxStaySeconds = state.staleSeconds;
    event.durationSeconds = state.staleSeconds;
    if (eventType == "jam_detected") emit jamOnReady(event);
    else emit jamOffReady(event);
}

QImage VideoPipeline::matToImage(const cv::Mat& frame) {
    cv::Mat rgb;
    cv::cvtColor(frame, rgb, cv::COLOR_BGR2RGB);
    return QImage(rgb.data, rgb.cols, rgb.rows, static_cast<int>(rgb.step), QImage::Format_RGB888).copy();
}

cv::Mat VideoPipeline::drawOverlay(const cv::Mat& frame, const DetectionResults& tracks, const QVector<RegionRuntimeState>& states) const {
    cv::Mat out = frame.clone();
    for (const RegionConfig& region : config_.camera.regions) {
        const std::vector<cv::Point> poly = Geometry::toCvPolygon(region.polygon);
        if (poly.size() >= 2) cv::polylines(out, poly, true, cv::Scalar(0, 255, 255), 2);
    }
    for (const DetectionResult& det : tracks) {
        cv::rectangle(out, det.box, cv::Scalar(0, 255, 0), 2);
        cv::putText(out, std::to_string(det.trackId), det.box.tl(), cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(0, 255, 0), 2);
    }
    int y = 28;
    for (const RegionRuntimeState& s : states) {
        const cv::Scalar color = s.jamActive ? cv::Scalar(0, 0, 255) : cv::Scalar(255, 255, 255);
        cv::putText(out, (s.id + ": count=" + QString::number(s.flowCount) + " inside=" + QString::number(s.insideCount)).toStdString(),
                    cv::Point(20, y), cv::FONT_HERSHEY_SIMPLEX, 0.6, color, 2);
        y += 24;
    }
    return out;
}
