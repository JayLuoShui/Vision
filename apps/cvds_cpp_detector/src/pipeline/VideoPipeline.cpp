#include "pipeline/VideoPipeline.h"

#include "utils/Geometry.h"

#include <QDir>
#include <QDateTime>
#include <QElapsedTimer>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace {

constexpr float kByteTrackLowConfidence = 0.1f;

bool isLiveSource(const QString& source) {
    bool numeric = false;
    source.toInt(&numeric);
    const QString lower = source.trimmed().toLower();
    return numeric || lower.startsWith("rtsp://") || lower.startsWith("rtmp://")
        || lower.startsWith("http://") || lower.startsWith("https://");
}

QJsonObject regionPayload(const RegionRuntimeState& state) {
    QJsonObject object;
    object.insert("id", state.id);
    object.insert("name", state.name);
    object.insert("flow_count", state.flowCount);
    object.insert("inside_count", state.insideCount);
    object.insert("max_inside_count", state.maxInsideCount);
    object.insert("jam_active", state.jamActive);
    object.insert("jam_count", state.jamCount);
    object.insert("status", state.status);
    object.insert("stale_seconds", state.jamActive ? state.staleSeconds : 0.0);
    return object;
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

VideoPipeline::VideoPipeline(Config config, QObject* parent)
    : QObject(parent), config_(std::move(config)), tracker_(0.3f, 30) {}

void VideoPipeline::stop() {
    stopRequested_.store(true);
}

bool VideoPipeline::validateConfig(QString* error) {
    if (config_.modelPath.trimmed().isEmpty() || !QFileInfo::exists(config_.modelPath)) {
        if (error) *error = "模型不存在：" + config_.modelPath;
        return false;
    }
    if (config_.sourcePath.trimmed().isEmpty()) {
        if (error) *error = "视频源不能为空";
        return false;
    }
    if (!isLiveSource(config_.sourcePath) && !QFileInfo::exists(config_.sourcePath)) {
        if (error) *error = "视频源不存在：" + config_.sourcePath;
        return false;
    }
    if (config_.outputDir.trimmed().isEmpty()) {
        if (error) *error = "输出目录不能为空";
        return false;
    }
    runtimeRegions_ = config_.regions.regions;
    bool totalRegionFound = false;
    const bool totalAll = config_.regions.totalCountRegionId == QStringLiteral("__all_count_regions__");
    for (RegionConfig& region : runtimeRegions_) {
        if (region.polygon.size() < 3 || !region.polygonClosed) {
            if (error) *error = "区域必须是闭合多边形：" + region.name;
            return false;
        }
        if (region.id == config_.regions.totalCountRegionId) totalRegionFound = true;
    }
    if (!totalAll && !runtimeRegions_.isEmpty() && !totalRegionFound) {
        if (error) *error = "总计区域不存在：" + config_.regions.totalCountRegionId;
        return false;
    }
    if (!config_.detectRoi.isEmpty() && config_.detectRoi.size() < 3) {
        if (error) *error = "检测 ROI 至少需要 3 个点";
        return false;
    }
    const QString transport = config_.rtspTransport.trimmed().toLower();
    if (transport != "tcp" && transport != "udp") {
        if (error) *error = "RTSP transport 只支持 tcp 或 udp";
        return false;
    }
    return true;
}

bool VideoPipeline::openCapture(cv::VideoCapture* capture, QString* error) const {
    const QString source = config_.sourcePath.trimmed();
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
    if (!opened && error) *error = "无法在超时时间内打开视频源：" + source;
    if (opened && isLiveSource(source)) {
        capture->set(cv::CAP_PROP_BUFFERSIZE, 1);
    }
    return opened;
}

bool VideoPipeline::readFrame(cv::VideoCapture* capture, cv::Mat* frame, QString* error) const {
    const int maxAttempts = isLiveSource(config_.sourcePath) ? 4 : 1;
    while (!stopRequested_.load()) {
        for (int attempt = 1; attempt <= maxAttempts; ++attempt) {
            QElapsedTimer timer;
            timer.start();
            const bool ok = capture->read(*frame);
            const qint64 elapsed = timer.elapsed();
            if (!ok || frame->empty()) {
                if (error) {
                    *error = isLiveSource(config_.sourcePath)
                        ? "视频流读取中断或超时：" + config_.sourcePath
                        : QString();
                }
                return false;
            }
            if (isLiveSource(config_.sourcePath) && elapsed > config_.readTimeoutMs) {
                if (error) *error = "视频流读取超时：" + QString::number(elapsed) + " ms";
                return false;
            }
            if (isLiveSource(config_.sourcePath) && isLowInformationFrame(*frame)) {
                if (attempt < maxAttempts) {
                    continue;
                }
                QThread::msleep(50);
                break;
            }
            return true;
        }
        if (!isLiveSource(config_.sourcePath)) {
            return false;
        }
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
            if (error) *error = "检测 ROI 超出画面或面积为 0";
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

void VideoPipeline::start() {
    stopRequested_.store(false);
    QString error;
    if (!validateConfig(&error)) {
        emit failed(error);
        return;
    }
    emit log("正在加载 " + inferenceBackendName(config_.backend) + " 模型");
    if (!detector_.load(config_.backend, config_.modelPath, config_.device, config_.inputSize, &error)) {
        emit failed(error);
        return;
    }

    cv::VideoCapture capture;
    if (!openCapture(&capture, &error)) {
        emit failed(error);
        return;
    }

    cv::Mat frame;
    if (!readFrame(&capture, &frame, &error)) {
        capture.release();
        emit failed(error.isEmpty() ? "视频源没有有效首帧" : error);
        return;
    }
    double sourceFps = capture.get(cv::CAP_PROP_FPS);
    if (!std::isfinite(sourceFps) || sourceFps <= 0.0) sourceFps = 25.0;
    if (!writer_.open(config_.outputDir, sourceFps, frame.size(), &error)) {
        capture.release();
        emit failed(error);
        return;
    }

    flowCounter_.configure(runtimeRegions_, config_.regions.totalCountRegionId);
    jamDetector_.configure(runtimeRegions_, config_.lowSpeedThreshold);
    configureTracker();
    emit log("开始视频检测与流量监测");

    FpsMeter inferFps;
    inferFps.reset();
    QVector<RegionRuntimeState> lastStates;
    int frameIndex = 0;
    const int previewEvery = std::max(1, static_cast<int>(std::round(sourceFps / std::max(1, config_.previewFps))));
    const int statsEvery = std::max(1, static_cast<int>(std::round(sourceFps / 5.0)));
    QString terminalError;

    while (!stopRequested_.load()) {
        ++frameIndex;
        QString inferError;
        const DetectionResults detections = inferFrame(frame, &inferError);
        if (!inferError.isEmpty()) {
            terminalError = inferError;
            break;
        }
        const DetectionResults tracks = tracker_.update(detections, 1.0 / sourceFps);
        QVector<RegionRuntimeState> states = flowCounter_.update(tracks);
        writer_.writeFlowEvents(flowCounter_.takeEntryEvents(), frameIndex);

        QHash<QString, QString> jamEvents;
        states = jamDetector_.update(states, tracker_.tracks(), &jamEvents);
        lastStates = states;
        for (auto it = jamEvents.constBegin(); it != jamEvents.constEnd(); ++it) {
            const RegionRuntimeState* state = findState(states, it.key());
            if (state) {
                if (!writer_.writeJamSignal(it.value(), *state, frameIndex, {}, &error)) {
                    terminalError = error;
                    break;
                }
                emitJamPayload(it.value(), *state, frameIndex);
            }
        }
        if (!terminalError.isEmpty()) break;

        cv::Mat overlay = drawOverlay(frame, tracks, states);
        writer_.writeFrame(overlay);
        if (frameIndex == 1 || frameIndex % statsEvery == 0 || !jamEvents.isEmpty()) {
            emitStatsPayload(frameIndex, states, static_cast<int>(tracks.size()));
        }
        const bool forcePreview = !jamEvents.isEmpty();
        if (forcePreview || frameIndex == 1 || frameIndex % previewEvery == 0) {
            writer_.writePreview(overlay);
            emitFramePayload(frameIndex, matToImage(overlay));
        }
        inferFps.addFrame();

        frame.release();
        if (!readFrame(&capture, &frame, &error)) {
            if (!error.isEmpty()) terminalError = error;
            break;
        }
        QThread::msleep(1);
    }

    QHash<QString, QString> clearEvents;
    lastStates = jamDetector_.clearActive(lastStates, &clearEvents);
    for (auto it = clearEvents.constBegin(); it != clearEvents.constEnd(); ++it) {
        const RegionRuntimeState* state = findState(lastStates, it.key());
        if (!state) continue;
        QString clearError;
        writer_.writeJamSignal(it.value(), *state, frameIndex, "monitor_stopped", &clearError);
        emitJamPayload(it.value(), *state, frameIndex, "monitor_stopped");
        if (terminalError.isEmpty() && !clearError.isEmpty()) terminalError = clearError;
    }

    QString summaryError;
    writer_.writeSummary(
        lastStates,
        config_.regions.totalCountRegionId,
        flowCounter_.totalCount(),
        frameIndex,
        &summaryError);
    writer_.close();
    capture.release();

    if (terminalError.isEmpty() && !summaryError.isEmpty()) terminalError = summaryError;
    if (!terminalError.isEmpty()) {
        emit failed(terminalError);
        return;
    }
    int jamCount = 0;
    int maxInsideCount = 0;
    const bool totalAll = config_.regions.totalCountRegionId == QStringLiteral("__all_count_regions__");
    QJsonArray finalRegions;
    for (const RegionRuntimeState& state : lastStates) {
        jamCount += state.jamCount;
        if (totalAll || state.id == config_.regions.totalCountRegionId) {
            maxInsideCount = std::max(maxInsideCount, state.maxInsideCount);
        }
        finalRegions.append(regionPayload(state));
    }
    QJsonObject donePayload;
    donePayload.insert("type", "done");
    donePayload.insert("frames", frameIndex);
    donePayload.insert("total_count_region", config_.regions.totalCountRegionId);
    donePayload.insert("total_count", flowCounter_.totalCount());
    donePayload.insert("flow_count", flowCounter_.totalCount());
    donePayload.insert("jam_count", jamCount);
    donePayload.insert("global_jam_count", jamCount);
    donePayload.insert("max_inside_count", maxInsideCount);
    donePayload.insert("regions", finalRegions);
    donePayload.insert(
        "output_video",
        QDir(config_.outputDir).filePath("cvds_online_parcel_flow_monitor.mp4"));
    donePayload.insert("events_csv", QDir(config_.outputDir).filePath("flow_events.csv"));
    donePayload.insert("jam_signals", QDir(config_.outputDir).filePath("jam_signals.jsonl"));
    donePayload.insert("summary_json", QDir(config_.outputDir).filePath("flow_summary.json"));
    emitDashboard(donePayload);
    emit done(
        QString("视频检测完成：总帧 %1，累计 %2。输出：%3")
            .arg(frameIndex)
            .arg(flowCounter_.totalCount())
            .arg(QDir(config_.outputDir).filePath("cvds_online_parcel_flow_monitor.mp4")));
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
    const bool totalAll = config_.regions.totalCountRegionId == QStringLiteral("__all_count_regions__");
    const RegionRuntimeState* total = totalAll ? nullptr : findState(states, config_.regions.totalCountRegionId);
    bool jamActive = false;
    bool occupied = false;
    int totalFlowCount = 0;
    int totalInsideCount = 0;
    QJsonArray regions;
    for (const RegionRuntimeState& state : states) {
        jamActive = jamActive || state.jamActive;
        occupied = occupied || state.insideCount > 0;
        if (totalAll) {
            totalFlowCount += state.flowCount;
            totalInsideCount += state.insideCount;
        }
        regions.append(regionPayload(state));
    }
    if (!totalAll && total != nullptr) {
        totalFlowCount = total->flowCount;
        totalInsideCount = total->insideCount;
    }
    QJsonObject payload;
    payload.insert("type", "frame");
    payload.insert("frame", frameIndex);
    payload.insert("preview_path", writer_.previewPath());
    payload.insert("total_count", totalFlowCount);
    payload.insert("flow_count", totalFlowCount);
    payload.insert("inside_count", totalInsideCount);
    payload.insert("tracked_count", trackedCount);
    payload.insert("jam_active", jamActive);
    payload.insert("global_status", jamActive ? "JAM" : (occupied ? "RUNNING" : "IDLE"));
    payload.insert("regions", regions);
    emitDashboard(payload);
}

void VideoPipeline::emitJamPayload(
    const QString& eventType,
    const RegionRuntimeState& state,
    int frameIndex,
    const QString& reason) {
    QJsonObject payload;
    payload.insert("type", "jam");
    payload.insert("event_type", eventType);
    payload.insert("timestamp_ms", QDateTime::currentMSecsSinceEpoch());
    payload.insert("frame", frameIndex);
    payload.insert("region_id", state.id);
    payload.insert("region_name", state.name);
    payload.insert("flow_count", state.flowCount);
    payload.insert("inside_count", state.insideCount);
    payload.insert("jam_count", state.jamCount);
    payload.insert("stale_seconds", state.staleSeconds);
    payload.insert("signal", eventType == "jam_detected" ? "IO_JAM_ON" : "IO_JAM_OFF");
    if (!reason.isEmpty()) payload.insert("reason", reason);
    emitDashboard(payload);
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
