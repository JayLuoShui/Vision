#include "pipeline/VideoPipeline.h"

#include "pipeline/DashboardPayloadBuilder.h"
#include "utils/FpsMeter.h"
#include "utils/Geometry.h"

#include <QDir>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QHash>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <algorithm>
#include <cmath>
#include <utility>
#include <vector>

namespace {

constexpr float kByteTrackLowConfidence = 0.1f;
constexpr double kFallbackSourceFps = 25.0;
constexpr double kStatsPayloadFps = 5.0;
constexpr int kLiveReadMaxAttempts = 4;
constexpr int kLowInformationRetrySleepMs = 50;
constexpr int kPipelineLoopSleepMs = 1;
constexpr const char* kOutputVideoName = "cvds_online_parcel_flow_monitor.mp4";

void setError(QString* error, QString message) {
    if (error) *error = std::move(message);
}

bool isTotalAllRegions(const QString& totalCountRegionId) {
    return totalCountRegionId == QStringLiteral("__all_count_regions__");
}

bool isLiveSource(const QString& source) {
    bool numeric = false;
    source.toInt(&numeric);
    const QString lower = source.trimmed().toLower();
    return numeric || lower.startsWith("rtsp://") || lower.startsWith("rtmp://")
        || lower.startsWith("http://") || lower.startsWith("https://");
}

double normalizeSourceFps(double fps) {
    return std::isfinite(fps) && fps > 0.0 ? fps : kFallbackSourceFps;
}

int frameInterval(double sourceFps, double targetFps) {
    return std::max(1, static_cast<int>(std::round(sourceFps / std::max(1.0, targetFps))));
}

const RegionRuntimeState* findState(
    const QVector<RegionRuntimeState>& states,
    const QString& regionId) {
    for (const RegionRuntimeState& state : states) {
        if (state.id == regionId) return &state;
    }
    return nullptr;
}

std::string overlayRegionLabel(const RegionRuntimeState& state) {
    return (state.id + ": " + QString::number(state.flowCount) + "/"
            + QString::number(state.insideCount) + " " + state.status)
        .toStdString();
}

bool trackCenterInsideFlowRegion(
    const DetectionResult& detection,
    const QVector<RegionConfig>& regions) {
    const cv::Point2f center = Geometry::boxCenter(detection.box);
    for (const RegionConfig& region : regions) {
        if (Geometry::pointInPolygon(center, region.polygon)) return true;
    }
    return false;
}

bool isLowInformationFrame(const cv::Mat& frame) {
    if (frame.empty() || frame.cols < 16 || frame.rows < 16) {
        return true;
    }
    cv::Mat gray;
    if (frame.channels() == 1) {
        gray = frame;
    } else {
        cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
    }
    cv::Scalar mean;
    cv::Scalar stddev;
    cv::meanStdDev(gray, mean, stddev);
    return stddev[0] < 3.0;
}

}  // namespace

struct VideoPipeline::PipelineRuntimeContext {
    cv::VideoCapture capture;
    cv::Mat frame;
    FpsMeter inferFps;
    QVector<RegionRuntimeState> lastStates;
    double sourceFps = kFallbackSourceFps;
    int previewEvery = 1;
    int statsEvery = 1;
    int frameIndex = 0;
    QString terminalError;
};

VideoPipeline::VideoPipeline(Config config, QObject* parent)
    : QObject(parent), config_(std::move(config)), tracker_(0.3f, 30) {}

void VideoPipeline::stop() {
    stopRequested_.store(true);
}

bool VideoPipeline::validateConfig(QString* error) {
    if (config_.modelPath.trimmed().isEmpty() || !QFileInfo::exists(config_.modelPath)) {
        setError(error, "模型不存在：" + config_.modelPath);
        return false;
    }
    if (config_.sourcePath.trimmed().isEmpty()) {
        setError(error, "视频源不能为空");
        return false;
    }
    if (!isLiveSource(config_.sourcePath) && !QFileInfo::exists(config_.sourcePath)) {
        setError(error, "视频源不存在：" + config_.sourcePath);
        return false;
    }
    if (config_.outputDir.trimmed().isEmpty()) {
        setError(error, "输出目录不能为空");
        return false;
    }

    runtimeRegions_ = config_.regions.regions;
    bool totalRegionFound = false;
    const bool totalAll = isTotalAllRegions(config_.regions.totalCountRegionId);
    for (const RegionConfig& region : runtimeRegions_) {
        if (region.polygon.size() < 3 || !region.polygonClosed) {
            setError(error, "区域必须是闭合多边形：" + region.name);
            return false;
        }
        if (region.id == config_.regions.totalCountRegionId) totalRegionFound = true;
    }
    if (!totalAll && !runtimeRegions_.isEmpty() && !totalRegionFound) {
        setError(error, "总计区域不存在：" + config_.regions.totalCountRegionId);
        return false;
    }
    if (!config_.detectRoi.isEmpty() && config_.detectRoi.size() < 3) {
        setError(error, "检测 ROI 至少需要 3 个点");
        return false;
    }
    const QString transport = config_.rtspTransport.trimmed().toLower();
    if (transport != "tcp" && transport != "udp") {
        setError(error, "RTSP transport 只支持 tcp 或 udp");
        return false;
    }
    return true;
}

bool VideoPipeline::initializeRuntime(PipelineRuntimeContext* context, QString* error) {
    emit log("正在加载 " + inferenceBackendName(config_.backend) + " 模型");
    if (!detector_.load(config_.backend, config_.modelPath, config_.device, config_.inputSize, error)) {
        return false;
    }

    if (!openCapture(&context->capture, error)) {
        return false;
    }

    if (!readFrame(&context->capture, &context->frame, error)) {
        context->capture.release();
        if (error && error->isEmpty()) *error = "视频源没有有效首帧";
        return false;
    }

    context->sourceFps = normalizeSourceFps(context->capture.get(cv::CAP_PROP_FPS));
    if (!writer_.open(config_.outputDir, context->sourceFps, context->frame.size(), error)) {
        context->capture.release();
        return false;
    }

    flowCounter_.configure(runtimeRegions_, config_.regions.totalCountRegionId);
    jamDetector_.configure(runtimeRegions_, config_.lowSpeedThreshold);
    configureTracker();

    context->inferFps.reset();
    context->previewEvery = frameInterval(context->sourceFps, config_.previewFps);
    context->statsEvery = frameInterval(context->sourceFps, kStatsPayloadFps);

    emit log("开始视频检测与流量监测");
    return true;
}

bool VideoPipeline::processCurrentFrame(PipelineRuntimeContext* context) {
    ++context->frameIndex;

    QString error;
    const DetectionResults detections = inferFrame(context->frame, &error);
    if (!error.isEmpty()) {
        context->terminalError = error;
        return false;
    }

    const DetectionResults tracks = tracker_.update(detections, 1.0 / context->sourceFps);
    QVector<RegionRuntimeState> states = flowCounter_.update(tracks);
    writer_.writeFlowEvents(flowCounter_.takeEntryEvents(), context->frameIndex);

    QHash<QString, QString> jamEvents;
    states = jamDetector_.update(states, tracker_.tracks(), &jamEvents);
    context->lastStates = states;
    if (!writeAndEmitJamEvents(jamEvents, states, context->frameIndex, {}, &error)) {
        context->terminalError = error;
        return false;
    }

    const bool forceDashboard = context->frameIndex == 1
        || context->frameIndex % context->statsEvery == 0
        || !jamEvents.isEmpty();
    const bool forcePreview = context->frameIndex == 1
        || context->frameIndex % context->previewEvery == 0
        || !jamEvents.isEmpty();

    cv::Mat overlay = drawOverlay(context->frame, tracks, states);
    writer_.writeFrame(overlay);
    if (forceDashboard) {
        emitStatsPayload(context->frameIndex, states, static_cast<int>(tracks.size()));
    }
    if (forcePreview) {
        writer_.writePreview(overlay);
        emitFramePayload(context->frameIndex, matToImage(overlay));
    }
    context->inferFps.addFrame();

    context->frame.release();
    if (!readFrame(&context->capture, &context->frame, &error)) {
        if (!error.isEmpty()) context->terminalError = error;
        return false;
    }
    QThread::msleep(kPipelineLoopSleepMs);
    return true;
}

void VideoPipeline::finishRuntime(PipelineRuntimeContext* context) {
    QHash<QString, QString> clearEvents;
    context->lastStates = jamDetector_.clearActive(context->lastStates, &clearEvents);

    QString clearError;
    if (!writeAndEmitJamEvents(
            clearEvents,
            context->lastStates,
            context->frameIndex,
            "monitor_stopped",
            &clearError)
        && context->terminalError.isEmpty()) {
        context->terminalError = clearError;
    }

    QString summaryError;
    writer_.writeSummary(
        context->lastStates,
        config_.regions.totalCountRegionId,
        flowCounter_.totalCount(),
        context->frameIndex,
        &summaryError);
    writer_.close();
    context->capture.release();

    if (context->terminalError.isEmpty() && !summaryError.isEmpty()) {
        context->terminalError = summaryError;
    }
}

void VideoPipeline::emitSuccess(const PipelineRuntimeContext& context) {
    emitDonePayload(context.lastStates, context.frameIndex);
    emit done(
        QString("视频检测完成：总帧 %1，累计 %2。输出：%3")
            .arg(context.frameIndex)
            .arg(flowCounter_.totalCount())
            .arg(QDir(config_.outputDir).filePath(kOutputVideoName)));
}

bool VideoPipeline::openCapture(cv::VideoCapture* capture, QString* error) const {
    const QString source = config_.sourcePath.trimmed();
    const bool live = isLiveSource(source);
    bool numeric = false;
    const int index = source.toInt(&numeric);

    bool opened = false;
    if (numeric) {
        opened = capture->open(index);
    } else {
        if (source.startsWith("rtsp://", Qt::CaseInsensitive)) {
            qputenv(
                "OPENCV_FFMPEG_CAPTURE_OPTIONS",
                ("rtsp_transport;" + config_.rtspTransport.trimmed().toLower()).toUtf8());
        }
        const std::vector<int> params = {
            cv::CAP_PROP_OPEN_TIMEOUT_MSEC, std::max(1, config_.openTimeoutMs),
            cv::CAP_PROP_READ_TIMEOUT_MSEC, std::max(1, config_.readTimeoutMs),
        };
        opened = capture->open(source.toStdString(), cv::CAP_FFMPEG, params);
    }

    if (!opened) setError(error, "无法在超时时间内打开视频源：" + source);
    if (opened && live) {
        capture->set(cv::CAP_PROP_BUFFERSIZE, 1);
    }
    return opened;
}

bool VideoPipeline::readFrame(cv::VideoCapture* capture, cv::Mat* frame, QString* error) const {
    const bool live = isLiveSource(config_.sourcePath);
    const int maxAttempts = live ? kLiveReadMaxAttempts : 1;

    while (!stopRequested_.load()) {
        for (int attempt = 1; attempt <= maxAttempts; ++attempt) {
            QElapsedTimer timer;
            timer.start();
            const bool ok = capture->read(*frame);
            const qint64 elapsed = timer.elapsed();

            if (!ok || frame->empty()) {
                setError(error, live ? "视频流读取中断或超时：" + config_.sourcePath : QString());
                return false;
            }
            if (live && elapsed > config_.readTimeoutMs) {
                setError(error, "视频流读取超时：" + QString::number(elapsed) + " ms");
                return false;
            }
            if (live && isLowInformationFrame(*frame)) {
                if (attempt < maxAttempts) {
                    continue;
                }
                QThread::msleep(kLowInformationRetrySleepMs);
                break;
            }
            return true;
        }
        if (!live) return false;
    }
    return false;
}

DetectionResults VideoPipeline::inferFrame(const cv::Mat& frame, QString* error) {
    cv::Mat inferenceFrame = frame;
    cv::Point offset;
    std::vector<cv::Point> roi;
    if (!config_.detectRoi.isEmpty()) {
        roi = Geometry::toCvPolygon(config_.detectRoi);
        cv::Rect bounds = cv::boundingRect(roi) & cv::Rect(0, 0, frame.cols, frame.rows);
        if (bounds.width <= 0 || bounds.height <= 0) {
            setError(error, "检测 ROI 超出画面或面积为 0");
            return {};
        }
        inferenceFrame = frame(bounds);
        offset = bounds.tl();
    }

    DetectionResults detections = detector_.infer(
        inferenceFrame,
        std::min(static_cast<float>(config_.confidence), kByteTrackLowConfidence),
        static_cast<float>(config_.iou),
        config_.classFilterId,
        error);
    for (DetectionResult& detection : detections) {
        detection.box.x += static_cast<float>(offset.x);
        detection.box.y += static_cast<float>(offset.y);
    }
    if (!roi.empty()) {
        detections.erase(
            std::remove_if(
                detections.begin(),
                detections.end(),
                [&](const DetectionResult& detection) {
                    return !Geometry::pointInPolygon(Geometry::boxCenter(detection.box), roi);
                }),
            detections.end());
    }
    return detections;
}

void VideoPipeline::configureTracker() {
    const float trackHigh = std::clamp(
        static_cast<float>(config_.confidence),
        kByteTrackLowConfidence,
        1.0f);
    tracker_ = ByteTrack(
        0.2f,
        30,
        trackHigh,
        kByteTrackLowConfidence,
        0.5f,
        trackHigh);
}

bool VideoPipeline::writeAndEmitJamEvents(
    const QHash<QString, QString>& events,
    const QVector<RegionRuntimeState>& states,
    int frameIndex,
    const QString& reason,
    QString* error) {
    for (auto it = events.constBegin(); it != events.constEnd(); ++it) {
        const RegionRuntimeState* state = findState(states, it.key());
        if (!state) continue;
        if (!writer_.writeJamSignal(it.value(), *state, frameIndex, reason, error)) {
            return false;
        }
        emitJamPayload(it.value(), *state, frameIndex, reason);
    }
    return true;
}

void VideoPipeline::start() {
    stopRequested_.store(false);

    QString error;
    if (!validateConfig(&error)) {
        emit failed(error);
        return;
    }

    PipelineRuntimeContext context;
    if (!initializeRuntime(&context, &error)) {
        emit failed(error);
        return;
    }

    while (!stopRequested_.load() && processCurrentFrame(&context)) {}

    finishRuntime(&context);
    if (!context.terminalError.isEmpty()) {
        emit failed(context.terminalError);
        return;
    }

    emitSuccess(context);
}

void VideoPipeline::emitDonePayload(const QVector<RegionRuntimeState>& states, int frameIndex) {
    emitDashboard(DashboardPayloadBuilder::buildDonePayload({
        frameIndex,
        config_.regions.totalCountRegionId,
        states,
        flowCounter_.totalCount(),
        config_.outputDir,
    }));
}

void VideoPipeline::emitDashboard(const QJsonObject& payload) {
    emit dashboardPayloadReady(QJsonDocument(payload).toJson(QJsonDocument::Compact));
}

void VideoPipeline::emitFramePayload(
    int frameIndex,
    const QImage& image) {
    Q_UNUSED(frameIndex);
    emit frameReady(image);
}

void VideoPipeline::emitStatsPayload(
    int frameIndex,
    const QVector<RegionRuntimeState>& states,
    int trackedCount) {
    emitDashboard(DashboardPayloadBuilder::buildFramePayload({
        frameIndex,
        writer_.previewPath(),
        config_.regions.totalCountRegionId,
        states,
        trackedCount,
    }));
}

void VideoPipeline::emitJamPayload(
    const QString& eventType,
    const RegionRuntimeState& state,
    int frameIndex,
    const QString& reason) {
    emitDashboard(DashboardPayloadBuilder::buildJamPayload({
        eventType,
        state,
        frameIndex,
        reason,
    }));
}

QImage VideoPipeline::matToImage(const cv::Mat& frame) {
    cv::Mat rgb;
    cv::cvtColor(frame, rgb, cv::COLOR_BGR2RGB);
    return QImage(
        rgb.data,
        rgb.cols,
        rgb.rows,
        static_cast<int>(rgb.step),
        QImage::Format_RGB888).copy();
}

cv::Mat VideoPipeline::drawOverlay(
    const cv::Mat& frame,
    const DetectionResults& tracks,
    const QVector<RegionRuntimeState>& states) const {
    cv::Mat out = frame.clone();
    if (!config_.detectRoi.isEmpty()) {
        const std::vector<cv::Point> polygon = Geometry::toCvPolygon(config_.detectRoi);
        cv::polylines(out, polygon, true, cv::Scalar(255, 170, 0), 2);
    }
    for (const RegionConfig& region : runtimeRegions_) {
        const RegionRuntimeState* state = findState(states, region.id);
        const bool jam = state && state->jamActive;
        const std::vector<cv::Point> polygon = Geometry::toCvPolygon(region.polygon);
        cv::polylines(
            out,
            polygon,
            true,
            jam ? cv::Scalar(0, 0, 255) : cv::Scalar(0, 210, 255),
            jam ? 4 : 2);
    }
    for (const DetectionResult& detection : tracks) {
        const cv::Rect rect(
            static_cast<int>(detection.box.x),
            static_cast<int>(detection.box.y),
            static_cast<int>(detection.box.width),
            static_cast<int>(detection.box.height));
        const bool insideFlowRoi = trackCenterInsideFlowRegion(detection, runtimeRegions_);
        const cv::Scalar boxColor = insideFlowRoi
            ? cv::Scalar(0, 220, 0)
            : cv::Scalar(0, 220, 255);
        cv::rectangle(out, rect, boxColor, 2);
        cv::putText(
            out,
            "ID " + std::to_string(detection.trackId),
            rect.tl(),
            cv::FONT_HERSHEY_SIMPLEX,
            0.6,
            boxColor,
            2);
    }
    int y = 32;
    for (const RegionRuntimeState& state : states) {
        cv::putText(
            out,
            overlayRegionLabel(state),
            cv::Point(20, y),
            cv::FONT_HERSHEY_SIMPLEX,
            0.65,
            state.jamActive ? cv::Scalar(0, 0, 255) : cv::Scalar(255, 255, 255),
            2);
        y += 28;
    }
    return out;
}
