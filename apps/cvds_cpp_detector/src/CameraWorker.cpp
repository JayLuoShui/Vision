#include "CameraWorker.h"

#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <QElapsedTimer>
#include <QThread>

#include <algorithm>
#include <utility>
#include <vector>

namespace {

QImage matToImage(const cv::Mat& bgr) {
    cv::Mat rgb;
    cv::cvtColor(bgr, rgb, cv::COLOR_BGR2RGB);
    return QImage(rgb.data, rgb.cols, rgb.rows, static_cast<int>(rgb.step), QImage::Format_RGB888).copy();
}

cv::VideoCapture openCapture(const QString& source, const QString& rtspTransport) {
    const QString trimmed = source.trimmed();
    bool isNumber = false;
    const int index = trimmed.toInt(&isNumber);
    if (isNumber) {
        return cv::VideoCapture(index);
    }
    if (trimmed.startsWith("rtsp://", Qt::CaseInsensitive)) {
        qputenv("OPENCV_FFMPEG_CAPTURE_OPTIONS", ("rtsp_transport;" + rtspTransport).toUtf8());
        const std::vector<int> params = {
            cv::CAP_PROP_OPEN_TIMEOUT_MSEC, 3000,
            cv::CAP_PROP_READ_TIMEOUT_MSEC, 3000,
        };
        return cv::VideoCapture(trimmed.toStdString(), cv::CAP_FFMPEG, params);
    }
    return cv::VideoCapture(trimmed.toStdString());
}

}  // namespace

CameraWorker::CameraWorker(CameraConfig config, QObject* parent)
    : QObject(parent),
      config_(std::move(config)) {
    snapshot_.cameraId = config_.cameraId;
    snapshot_.lineId = config_.lineId;
    snapshot_.beltId = config_.beltId;
}

void CameraWorker::run() {
    stopped_ = false;
    const int frameIntervalMs = std::max(1, 1000 / std::max(1, config_.targetFps));
    const int reconnectMs = std::max(1000, config_.reconnectSeconds * 1000);
    int framesInWindow = 0;
    QElapsedTimer fpsTimer;
    fpsTimer.start();

    while (!stopped_) {
        emit log(QString("[%1] 正在连接视频源。").arg(config_.cameraId));
        cv::VideoCapture capture = openCapture(config_.source, config_.rtspTransport);
        if (!capture.isOpened()) {
            emitSnapshot("OFFLINE", "无法打开视频源");
            emit failed(config_.cameraId, "无法打开视频源");
            QThread::msleep(static_cast<unsigned long>(reconnectMs));
            continue;
        }

        snapshot_.frameWidth = static_cast<int>(capture.get(cv::CAP_PROP_FRAME_WIDTH));
        snapshot_.frameHeight = static_cast<int>(capture.get(cv::CAP_PROP_FRAME_HEIGHT));
        snapshot_.droppedFrames = 0;
        emitSnapshot("ONLINE");

        while (!stopped_) {
            cv::Mat frame;
            if (!capture.read(frame) || frame.empty()) {
                snapshot_.droppedFrames += 1;
                emitSnapshot("RECONNECTING", "视频流读取中断");
                emit failed(config_.cameraId, "视频流读取中断，准备重连");
                break;
            }

            snapshot_.frameWidth = frame.cols;
            snapshot_.frameHeight = frame.rows;
            ++framesInWindow;
            if (fpsTimer.elapsed() >= 1000) {
                snapshot_.decodeFps = framesInWindow * 1000.0 / std::max<qint64>(1, fpsTimer.elapsed());
                framesInWindow = 0;
                fpsTimer.restart();
                emitSnapshot("ONLINE");
            }
            emit frameReady(config_.cameraId, matToImage(frame));
            QThread::msleep(static_cast<unsigned long>(frameIntervalMs));
        }
        capture.release();
        if (!stopped_) {
            QThread::msleep(static_cast<unsigned long>(reconnectMs));
        }
    }

    emitSnapshot("OFFLINE");
    emit finished(config_.cameraId);
}

void CameraWorker::stop() {
    stopped_ = true;
}

void CameraWorker::emitSnapshot(const QString& status, const QString& error) {
    snapshot_.status = status;
    snapshot_.error = error;
    emit snapshotReady(snapshot_);
}
