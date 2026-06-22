#include "MainWindow.h"
#include "RuntimePaths.h"

#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <QCheckBox>
#include <QComboBox>
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QDoubleSpinBox>
#include <QFile>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QFrame>
#include <QGridLayout>
#include <QGroupBox>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QKeyEvent>
#include <QKeySequence>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QMetaObject>
#include <QMouseEvent>
#include <QPainter>
#include <QPlainTextEdit>
#include <QPolygon>
#include <QProcess>
#include <QPushButton>
#include <QPixmap>
#include <QResizeEvent>
#include <QScrollArea>
#include <QScrollBar>
#include <QSettings>
#include <QSignalBlocker>
#include <QSizePolicy>
#include <QSpinBox>
#include <QSplitter>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#include <QWheelEvent>

#include <algorithm>
#include <stdexcept>

namespace {

class ScrollSafeSpinBox : public QSpinBox {
public:
    using QSpinBox::QSpinBox;

protected:
    void wheelEvent(QWheelEvent* event) override {
        event->ignore();
    }
};

class ScrollSafeDoubleSpinBox : public QDoubleSpinBox {
public:
    using QDoubleSpinBox::QDoubleSpinBox;

protected:
    void wheelEvent(QWheelEvent* event) override {
        event->ignore();
    }
};

class ScrollSafeComboBox : public QComboBox {
public:
    using QComboBox::QComboBox;

protected:
    void wheelEvent(QWheelEvent* event) override {
        event->ignore();
    }
};

QImage matToImage(const cv::Mat& bgr) {
    cv::Mat rgb;
    cv::cvtColor(bgr, rgb, cv::COLOR_BGR2RGB);
    return QImage(rgb.data, rgb.cols, rgb.rows, static_cast<int>(rgb.step), QImage::Format_RGB888).copy();
}

QStringList inspectModelArgs(const QString& modelPath) {
    return {"inspect-model", "--model", modelPath};
}

QStringList parseClassLabelsFromJson(const QByteArray& outputBytes) {
    const QJsonDocument document = QJsonDocument::fromJson(outputBytes);
    if (!document.isObject()) {
        return {};
    }
    const QJsonArray labelsArray = document.object().value("class_names").toArray();
    QStringList labels;
    for (const QJsonValue& value : labelsArray) {
        const QString text = value.toString().trimmed();
        if (!text.isEmpty()) {
            labels.push_back(text);
        }
    }
    return labels;
}

bool canBeRuntimeSource(const QString& source) {
    const QString trimmed = source.trimmed();
    bool isNumber = false;
    const int cameraIndex = trimmed.toInt(&isNumber);
    return trimmed.startsWith("rtsp://", Qt::CaseInsensitive)
        || trimmed.startsWith("http://", Qt::CaseInsensitive)
        || trimmed.startsWith("https://", Qt::CaseInsensitive)
        || trimmed.contains("://")
        || (isNumber && cameraIndex >= 0);
}

QString sourcePathForSettings(const QString& source) {
    const QString trimmed = source.trimmed();
    const QUrl url(trimmed);
    if (!url.isValid() || url.scheme().isEmpty()) {
        return trimmed;
    }
    return url.toString(QUrl::RemoveUserInfo | QUrl::FullyEncoded);
}

QString privatePath(const QLineEdit* edit) {
    return edit == nullptr ? QString() : edit->property("fullPath").toString().trimmed();
}

QString privatePathLabel(const QString& path) {
    const QString trimmed = path.trimmed();
    if (trimmed.isEmpty()) {
        return "未选择";
    }

    bool isCameraIndex = false;
    const int cameraIndex = trimmed.toInt(&isCameraIndex);
    if (isCameraIndex && cameraIndex >= 0) {
        return "摄像头 " + QString::number(cameraIndex);
    }

    if (trimmed.contains("://")) {
        const QUrl url(trimmed);
        const QString host = url.host().isEmpty() ? "网络视频流" : url.host();
        return url.scheme().toUpper() + " · " + host;
    }

    const QFileInfo info(trimmed);
    const QString name = info.fileName();
    return name.isEmpty() ? "已选择目录" : name;
}

void setPrivatePath(QLineEdit* edit, const QString& path, bool revealFull = false) {
    if (edit == nullptr) {
        return;
    }
    const QString trimmed = path.trimmed();
    edit->setProperty("fullPath", trimmed);
    edit->setText(revealFull ? trimmed : privatePathLabel(trimmed));
    edit->setCursorPosition(0);
    if (!revealFull || trimmed.isEmpty()) {
        return;
    }
    QTimer::singleShot(5000, edit, [edit, trimmed]() {
        if (privatePath(edit) == trimmed) {
            edit->setText(privatePathLabel(trimmed));
            edit->setCursorPosition(0);
        }
    });
}

cv::VideoCapture openCapture(const QString& source) {
    const QString trimmed = source.trimmed();
    bool isNumber = false;
    const int index = trimmed.toInt(&isNumber);
    if (isNumber) {
        return cv::VideoCapture(index);
    }
    return cv::VideoCapture(trimmed.toStdString());
}

QString findDefaultModelPath() {
    const QDir weightsDir(RuntimePaths::defaultWeightsDir());
    const QStringList files = weightsDir.entryList({"*.pt", "*.onnx", "*.xml"}, QDir::Files, QDir::Name);
    if (!files.isEmpty()) {
        return weightsDir.filePath(files.first());
    }
    const QStringList directories = weightsDir.entryList(
        {"*_openvino_model"},
        QDir::Dirs | QDir::NoDotAndDotDot,
        QDir::Name
    );
    if (!directories.isEmpty()) {
        return weightsDir.filePath(directories.first());
    }
    return {};
}

bool isOutputDirWritable(const QString& outputDir, QString* errorMessage = nullptr) {
    if (outputDir.trimmed().isEmpty()) {
        if (errorMessage != nullptr) {
            *errorMessage = "输出目录为空。";
        }
        return false;
    }
    QDir dir(outputDir);
    if (!dir.exists() && !QDir().mkpath(outputDir)) {
        if (errorMessage != nullptr) {
            *errorMessage = "无法创建输出目录。";
        }
        return false;
    }
    const QString probePath = dir.filePath(".cvds_write_test.tmp");
    QFile probe(probePath);
    if (!probe.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        if (errorMessage != nullptr) {
            *errorMessage = "输出目录不可写。";
        }
        return false;
    }
    probe.write("ok");
    probe.close();
    QFile::remove(probePath);
    return true;
}

RegionRuntimeState buildFallbackState(const RegionConfig& region) {
    RegionRuntimeState state;
    state.id = region.id;
    state.name = region.name;
    state.status = "待机";
    return state;
}

QString regionStatusText(const RegionRuntimeState& state, bool running) {
    if (state.jamActive) {
        return "堵包";
    }
    const QString status = state.status.trimmed().toUpper();
    if (status == "RUNNING") {
        return "运行中";
    }
    if (status == "IDLE") {
        return "空闲";
    }
    if (status == "JAM") {
        return "堵包";
    }
    if (status == "ERROR") {
        return "异常";
    }
    if (!state.status.trimmed().isEmpty()) {
        return state.status.trimmed();
    }
    return running ? "运行中" : "待机";
}

QString dashboardStatusForStates(
    const QVector<RegionRuntimeState>& states,
    bool jamActive,
    const QString& fallback
) {
    if (jamActive) {
        return "堵包";
    }
    if (!states.isEmpty()) {
        const bool allIdle = std::all_of(states.cbegin(), states.cend(), [](const RegionRuntimeState& state) {
            return state.insideCount <= 0;
        });
        return allIdle ? "空闲" : "运行中";
    }
    const QString normalized = fallback.trimmed().toUpper();
    if (normalized == "RUNNING") {
        return "运行中";
    }
    if (normalized == "IDLE") {
        return "空闲";
    }
    if (normalized == "JAM") {
        return "堵包";
    }
    if (normalized == "ERROR") {
        return "异常";
    }
    return fallback;
}

}  // namespace

RoiPreviewLabel::RoiPreviewLabel(QWidget* parent)
    : QLabel(parent) {
    setMinimumSize(160, 90);
    setMouseTracking(true);
    setFocusPolicy(Qt::StrongFocus);
    setText("请选择视频源，首帧会显示在这里。");
}

void RoiPreviewLabel::setImage(const QImage& image) {
    image_ = image;
    update();
}

void RoiPreviewLabel::setDrawMode(DrawMode mode) {
    drawMode_ = mode;
    hasDraftCursor_ = false;
    setFocus();
    update();
}

void RoiPreviewLabel::setFlowRegions(const QVector<RegionConfig>& regions) {
    flowRegions_ = regions;
    if (flowRegions_.isEmpty()) {
        activeRegionId_.clear();
        flowRoi_.clear();
        flowRoiClosed_ = false;
        update();
        return;
    }
    if (activeRegionId_.trimmed().isEmpty() || activeRegionIndex() < 0) {
        activeRegionId_ = flowRegions_.first().id;
    }
    const int index = activeRegionIndex();
    if (index >= 0) {
        flowRoi_ = flowRegions_[index].polygon;
        flowRoiClosed_ = flowRegions_[index].polygonClosed;
    }
    update();
}

void RoiPreviewLabel::setActiveRegionId(const QString& regionId) {
    activeRegionId_ = regionId.trimmed();
    const int index = activeRegionIndex();
    if (index >= 0) {
        flowRoi_ = flowRegions_[index].polygon;
        flowRoiClosed_ = flowRegions_[index].polygonClosed;
    } else {
        flowRoi_.clear();
        flowRoiClosed_ = false;
    }
    hasDraftCursor_ = false;
    update();
}

void RoiPreviewLabel::setJamRegionIds(const QStringList& regionIds) {
    jamRegionIds_ = regionIds;
    update();
}

void RoiPreviewLabel::setAlertFlashVisible(bool visible) {
    alertFlashVisible_ = visible;
    update();
}

void RoiPreviewLabel::setRoiEditingEnabled(bool enabled) {
    roiEditingEnabled_ = enabled;
    if (!enabled) {
        hasDraftCursor_ = false;
    }
}

void RoiPreviewLabel::clearCurrentRoi() {
    activePolygon().clear();
    activeRoiClosed() = false;
    hasDraftCursor_ = false;
    syncActiveFlowRegion();
    emitCurrentRoi();
    update();
}

void RoiPreviewLabel::undoCurrentPoint() {
    QVector<QPoint>& polygon = activePolygon();
    if (!polygon.isEmpty()) {
        polygon.removeLast();
    }
    activeRoiClosed() = false;
    hasDraftCursor_ = false;
    syncActiveFlowRegion();
    emitCurrentRoi();
    update();
}

void RoiPreviewLabel::finishCurrentPolygon() {
    hasDraftCursor_ = false;
    activeRoiClosed() = activePolygon().size() >= 3;
    syncActiveFlowRegion();
    emitCurrentRoi();
    update();
}

void RoiPreviewLabel::setFlowRoiFromText(const QString& text) {
    flowRoi_ = textToPolygon(text);
    flowRoiClosed_ = flowRoi_.size() >= 3;
    syncActiveFlowRegion();
    update();
}

void RoiPreviewLabel::setDetectRoiFromText(const QString& text) {
    detectRoi_ = textToPolygon(text);
    detectRoiClosed_ = detectRoi_.size() >= 3;
    update();
}

QString RoiPreviewLabel::flowRoiText() const {
    return polygonToText(flowRoi_, flowRoiClosed_);
}

QString RoiPreviewLabel::detectRoiText() const {
    return polygonToText(detectRoi_, detectRoiClosed_);
}

QRect RoiPreviewLabel::imageRectInLabel() const {
    if (image_.isNull()) {
        return {};
    }
    QSize scaled = image_.size();
    scaled.scale(size(), Qt::KeepAspectRatio);
    const int left = (width() - scaled.width()) / 2;
    const int top = (height() - scaled.height()) / 2;
    return QRect(QPoint(left, top), scaled);
}

QPoint RoiPreviewLabel::labelToImagePoint(const QPoint& point) const {
    const QRect imageRect = imageRectInLabel();
    if (image_.isNull() || imageRect.isEmpty()) {
        return {};
    }
    const int x = std::clamp(point.x(), imageRect.left(), imageRect.right());
    const int y = std::clamp(point.y(), imageRect.top(), imageRect.bottom());
    const double sx = static_cast<double>(image_.width()) / std::max(1, imageRect.width());
    const double sy = static_cast<double>(image_.height()) / std::max(1, imageRect.height());
    return QPoint(
        std::clamp(static_cast<int>((x - imageRect.left()) * sx), 0, image_.width() - 1),
        std::clamp(static_cast<int>((y - imageRect.top()) * sy), 0, image_.height() - 1)
    );
}

QPoint RoiPreviewLabel::imageToLabelPoint(const QPoint& point) const {
    const QRect imageRect = imageRectInLabel();
    if (image_.isNull() || imageRect.isEmpty()) {
        return {};
    }
    const double sx = static_cast<double>(imageRect.width()) / std::max(1, image_.width());
    const double sy = static_cast<double>(imageRect.height()) / std::max(1, image_.height());
    return QPoint(
        imageRect.left() + static_cast<int>(point.x() * sx),
        imageRect.top() + static_cast<int>(point.y() * sy)
    );
}

int RoiPreviewLabel::activeRegionIndex() const {
    for (int i = 0; i < flowRegions_.size(); ++i) {
        if (flowRegions_[i].id == activeRegionId_) {
            return i;
        }
    }
    return -1;
}

void RoiPreviewLabel::syncActiveFlowRegion() {
    if (drawMode_ != DrawMode::FlowRoi && activeRegionIndex() < 0) {
        return;
    }
    const int index = activeRegionIndex();
    if (index >= 0) {
        flowRegions_[index].polygon = flowRoi_;
        flowRegions_[index].polygonClosed = flowRoiClosed_;
    }
}

QVector<QPoint>& RoiPreviewLabel::activePolygon() {
    return drawMode_ == DrawMode::FlowRoi ? flowRoi_ : detectRoi_;
}

const QVector<QPoint>& RoiPreviewLabel::activePolygon() const {
    return drawMode_ == DrawMode::FlowRoi ? flowRoi_ : detectRoi_;
}

bool& RoiPreviewLabel::activeRoiClosed() {
    return drawMode_ == DrawMode::FlowRoi ? flowRoiClosed_ : detectRoiClosed_;
}

bool RoiPreviewLabel::activeRoiClosed() const {
    return drawMode_ == DrawMode::FlowRoi ? flowRoiClosed_ : detectRoiClosed_;
}

QString RoiPreviewLabel::polygonToText(const QVector<QPoint>& polygon, bool closed) const {
    if (!closed || polygon.size() < 3) {
        return {};
    }
    return ::polygonToText(polygon);
}

QVector<QPoint> RoiPreviewLabel::textToPolygon(const QString& text) const {
    try {
        return polygonFromText(text, "ROI", true);
    } catch (const std::exception&) {
        return {};
    }
}

void RoiPreviewLabel::emitCurrentRoi() {
    if (drawMode_ == DrawMode::FlowRoi) {
        emit flowRegionChanged(activeRegionId_, activePolygon(), activeRoiClosed());
    }
    emit roiChanged(drawMode_, polygonToText(activePolygon(), activeRoiClosed()));
}

void RoiPreviewLabel::drawPolygon(QPainter& painter, const QVector<QPoint>& polygon, bool closed, const QColor& color, const QString& label) const {
    if (polygon.isEmpty()) {
        return;
    }
    QPolygon mapped;
    mapped.reserve(polygon.size());
    for (const QPoint& point : polygon) {
        mapped << imageToLabelPoint(point);
    }

    painter.setPen(QPen(color, 2));
    painter.setBrush(QColor(color.red(), color.green(), color.blue(), closed && polygon.size() >= 3 ? 35 : 0));
    if (closed && mapped.size() >= 3) {
        painter.drawPolygon(mapped);
    } else if (mapped.size() >= 2) {
        painter.drawPolyline(mapped);
    }

    painter.setBrush(color);
    for (const QPoint& point : mapped) {
        painter.drawEllipse(point, 4, 4);
    }
    painter.setPen(color);
    painter.drawText(mapped.first() + QPoint(8, -8), label);
}

void RoiPreviewLabel::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event);
    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.fillRect(rect(), QColor("#080D13"));

    const QRect imageRect = imageRectInLabel();
    if (image_.isNull() || imageRect.isEmpty()) {
        painter.setPen(QColor("#8FA5B8"));
        painter.drawText(rect(), Qt::AlignCenter, text());
        return;
    }

    painter.drawImage(imageRect, image_);
    painter.fillRect(QRect(0, 0, width(), imageRect.top()), QColor(5, 9, 18, 160));
    painter.fillRect(QRect(0, imageRect.bottom() + 1, width(), height() - imageRect.bottom() - 1), QColor(5, 9, 18, 160));

    for (const RegionConfig& region : flowRegions_) {
        const bool isCurrent = region.id == activeRegionId_;
        const bool jamActive = jamRegionIds_.contains(region.id);
        const QColor color = jamActive && alertFlashVisible_
            ? QColor("#F25555")
            : (isCurrent ? QColor("#2F88F5") : QColor("#FFB84D"));
        if (isCurrent) {
            drawPolygon(painter, flowRoi_, flowRoiClosed_, color, region.name + "（当前区域）");
        } else {
            drawPolygon(painter, region.polygon, region.polygonClosed, color, region.name);
        }
    }
    drawPolygon(painter, detectRoi_, detectRoiClosed_, QColor("#36BFD3"), "检测ROI");

    const QVector<QPoint>& polygon = activePolygon();
    if (hasDraftCursor_ && !polygon.isEmpty() && !activeRoiClosed()) {
        painter.setPen(QPen(QColor("#4DA3FF"), 2, Qt::DashLine));
        painter.drawLine(imageToLabelPoint(polygon.last()), imageToLabelPoint(draftCursor_));
        painter.setBrush(QColor("#4DA3FF"));
        painter.drawEllipse(imageToLabelPoint(draftCursor_), 4, 4);
    }

    painter.setPen(QColor("#F3F7FA"));
    painter.drawText(imageRect.adjusted(12, 18, -12, -18), Qt::AlignLeft | Qt::AlignTop, "当前区域: " + activeRegionId_);
    if (alertFlashVisible_ && !jamRegionIds_.isEmpty()) {
        painter.setPen(QPen(QColor("#F25555"), 4));
        painter.setBrush(Qt::NoBrush);
        painter.drawRect(rect().adjusted(2, 2, -2, -2));
    }
}

void RoiPreviewLabel::mousePressEvent(QMouseEvent* event) {
    if (!roiEditingEnabled_) {
        event->ignore();
        return;
    }
    if (image_.isNull()) {
        return;
    }
    setFocus();
    if (event->button() == Qt::RightButton) {
        finishCurrentPolygon();
        event->accept();
        return;
    }
    if (event->button() != Qt::LeftButton) {
        return;
    }
    if (drawMode_ == DrawMode::FlowRoi && activeRegionId_.trimmed().isEmpty()) {
        return;
    }
    if (activeRoiClosed()) {
        activePolygon().clear();
    }
    activeRoiClosed() = false;
    activePolygon().push_back(labelToImagePoint(event->pos()));
    hasDraftCursor_ = false;
    syncActiveFlowRegion();
    emitCurrentRoi();
    update();
    event->accept();
}

void RoiPreviewLabel::mouseMoveEvent(QMouseEvent* event) {
    if (!roiEditingEnabled_ || image_.isNull() || activePolygon().isEmpty() || activeRoiClosed()) {
        return;
    }
    draftCursor_ = labelToImagePoint(event->pos());
    hasDraftCursor_ = true;
    update();
}

void RoiPreviewLabel::keyPressEvent(QKeyEvent* event) {
    if (!roiEditingEnabled_) {
        QLabel::keyPressEvent(event);
        return;
    }
    if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter) {
        finishCurrentPolygon();
        event->accept();
        return;
    }
    if (event->key() == Qt::Key_Escape
        || event->key() == Qt::Key_Backspace
        || event->matches(QKeySequence::Undo)) {
        undoCurrentPoint();
        event->accept();
        return;
    }
    QLabel::keyPressEvent(event);
}

DetectionWorker::DetectionWorker(DetectJobConfig config)
    : config_(std::move(config)) {}

void DetectionWorker::stop() {
    stopped_ = true;
}

void DetectionWorker::run() {
    try {
        if (!QFileInfo::exists(config_.workerPath)) {
            throw std::runtime_error("缺少 worker exe");
        }
        if (!QFileInfo::exists(config_.modelPath)) {
            throw std::runtime_error("模型不存在");
        }
        if (!QFileInfo::exists(config_.trackerPath)) {
            throw std::runtime_error("缺少 tracker yaml");
        }
        if (!QFileInfo::exists(config_.regionsPath)) {
            throw std::runtime_error("缺少 regions.json");
        }
        QDir().mkpath(config_.outputDir);
        const QString previewPath = QDir(config_.outputDir).filePath("cvds_preview.jpg");
        QStringList args = {
            "detect",
            "--model", config_.modelPath,
            "--source", config_.sourcePath,
            "--rtsp-transport", config_.rtspTransport,
            "--output-dir", config_.outputDir,
            "--preview-path", previewPath,
            "--regions", config_.regionsPath,
            "--conf", QString::number(config_.confidence, 'f', 3),
            "--iou", QString::number(config_.iou, 'f', 3),
            "--imgsz", QString::number(config_.inputSize),
            "--device", config_.device,
            "--class-id", QString::number(config_.classFilterId),
            "--preview-fps", QString::number(config_.previewFps),
            "--jam-seconds", QString::number(config_.jamSeconds),
            "--jam-signal-path", config_.jamSignalPath,
            "--tracker", config_.trackerPath
        };
        if (!config_.detectRoiText.trimmed().isEmpty()) {
            args << "--detect-roi" << config_.detectRoiText.trimmed();
        }

        emit log("程序版本：" + RuntimePaths::versionText());
        emit log("worker：" + QFileInfo(config_.workerPath).fileName());
        emit log("模型：" + QFileInfo(config_.modelPath).fileName());
        emit log("输出目录：已配置");
        emit log("区域配置：" + QFileInfo(config_.regionsPath).fileName());
        emit log("检测模式：通过统一 worker 执行 PT / ONNX / OpenVINO 推理。");
        emit log("请求推理设备：" + config_.device);
        emit log("堵包信号文件：" + QFileInfo(config_.jamSignalPath).fileName());
        QProcess process;
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start(config_.workerPath, args);
        if (!process.waitForStarted(5000)) {
            throw std::runtime_error("检测进程启动失败");
        }

        QByteArray buffer;
        QString doneSummary;
        QString errorMessage;
        auto consumeLines = [&]() {
            while (true) {
                const int newlineIndex = buffer.indexOf('\n');
                if (newlineIndex < 0) {
                    break;
                }
                const QByteArray rawLine = buffer.left(newlineIndex).trimmed();
                buffer.remove(0, newlineIndex + 1);
                if (rawLine.isEmpty()) {
                    continue;
                }
                QJsonParseError parseError;
                const QJsonDocument document = QJsonDocument::fromJson(rawLine, &parseError);
                if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
                    emit log(QString::fromUtf8(rawLine));
                    continue;
                }
                const QJsonObject object = document.object();
                const QString type = object.value("type").toString();
                if (type == "status") {
                    QString message = object.value("message").toString();
                    if (object.contains("device")) {
                        message += "，实际推理设备：" + object.value("device").toString();
                    }
                    emit log(message);
                } else if (type == "frame") {
                    const QString path = object.value("preview_path").toString();
                    const QImage image(path);
                    if (!image.isNull()) {
                        emit frameReady(image);
                    }
                    emit dashboardPayloadReady(rawLine);
                } else if (type == "jam" || type == "jam_clear" || type == "done") {
                    emit dashboardPayloadReady(rawLine);
                    if (type == "done") {
                        const int totalCount = object.value("total_count").toInt(object.value("flow_count").toInt());
                        doneSummary = QString("视频检测完成：总帧 %1，累计 %2，堵包 %3 次，最大同时在区域内 %4。输出：%5")
                            .arg(object.value("frames").toInt())
                            .arg(totalCount)
                            .arg(object.value("jam_count").toInt())
                            .arg(object.value("max_inside_count").toInt())
                            .arg(object.value("output_video").toString());
                    }
                } else if (type == "error") {
                    errorMessage = object.value("message").toString();
                    emit log("检测错误：" + errorMessage);
                } else {
                    emit log(QString::fromUtf8(rawLine));
                }
            }
        };

        while (process.state() != QProcess::NotRunning) {
            if (stopped_) {
                process.kill();
                process.waitForFinished(3000);
                emit done("视频检测已停止。");
                return;
            }
            process.waitForReadyRead(100);
            buffer += process.readAllStandardOutput();
            consumeLines();
        }
        buffer += process.readAllStandardOutput();
        if (!buffer.trimmed().isEmpty()) {
            buffer += '\n';
            consumeLines();
        }

        if (process.exitCode() != 0) {
            emit failed(errorMessage.isEmpty() ? "检测进程异常退出，请查看日志。" : errorMessage);
            return;
        }
        emit done(doneSummary.isEmpty() ? "视频检测完成。" : doneSummary);
    } catch (const std::exception& ex) {
        emit failed(QString::fromUtf8(ex.what()));
    }
}

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent) {
    setWindowTitle("CVDS在线包裹流量监测 " + RuntimePaths::versionText());
    resize(800, 420);
    setMinimumSize(800, 420);

    auto* root = new QWidget(this);
    root->setObjectName("dashboardRoot");
    dashboardRoot_ = root;
    auto* layout = new QVBoxLayout(root);
    layout->setContentsMargins(6, 6, 6, 6);
    layout->setSpacing(6);

    auto* brandBar = new QFrame(root);
    brandBar->setObjectName("brandBar");
    brandBar->setFixedHeight(42);
    auto* brandLayout = new QHBoxLayout(brandBar);
    brandLayout->setContentsMargins(9, 4, 9, 4);
    brandLayout->setSpacing(8);

    auto* brandLogo = new QLabel(brandBar);
    brandLogo->setObjectName("brandLogo");
    brandLogo->setFixedSize(28, 28);
    brandLogo->setAlignment(Qt::AlignCenter);
    brandLogo->setPixmap(
        QPixmap(":/branding/cogy_mark.png").scaled(
            brandLogo->size(),
            Qt::KeepAspectRatio,
            Qt::SmoothTransformation
        )
    );

    auto* productTextLayout = new QVBoxLayout();
    productTextLayout->setContentsMargins(0, 0, 0, 0);
    productTextLayout->setSpacing(0);
    auto* productTitle = new QLabel("氪技 COGY · CVDS ONLINE PARCEL FLOW MONITOR", brandBar);
    productTitle->setObjectName("brandTitle");
    auto* productSubtitle = new QLabel("在线包裹流量监测", brandBar);
    productSubtitle->setObjectName("brandSubtitle");
    productTextLayout->addWidget(productTitle);
    productTextLayout->addWidget(productSubtitle);

    auto* versionLabel = new QLabel("V" + RuntimePaths::versionText(), brandBar);
    versionLabel->setObjectName("versionBadge");
    sourceStatusLabel_ = new QLabel("●  未选择视频源", brandBar);
    sourceStatusLabel_->setObjectName("connectionPill");
    channelStatusLabel_ = new QLabel("通道 --", brandBar);
    channelStatusLabel_->setObjectName("channelStatus");
    clockLabel_ = new QLabel(brandBar);
    clockLabel_->setObjectName("runtimeClock");
    systemStatusLabel_ = new QLabel("●  系统就绪", brandBar);
    systemStatusLabel_->setObjectName("systemStatus");

    brandLayout->addWidget(brandLogo);
    brandLayout->addLayout(productTextLayout);
    brandLayout->addStretch(1);
    brandLayout->addWidget(sourceStatusLabel_);
    brandLayout->addWidget(channelStatusLabel_);
    brandLayout->addWidget(clockLabel_);
    brandLayout->addWidget(versionLabel);
    brandLayout->addWidget(systemStatusLabel_);
    layout->addWidget(brandBar);

    mainSplitter_ = new QSplitter(Qt::Horizontal, root);
    auto* splitter = mainSplitter_;
    splitter->setObjectName("mainSplitter");
    splitter->setChildrenCollapsible(false);
    splitter->setHandleWidth(5);

    auto* leftShell = new QWidget(root);
    settingsPanel_ = leftShell;
    leftShell->setObjectName("settingsPanel");
    leftShell->setMinimumWidth(210);
    leftShell->setMaximumWidth(340);
    auto* leftLayout = new QVBoxLayout(leftShell);
    leftLayout->setContentsMargins(0, 0, 4, 0);
    leftLayout->setSpacing(0);

    auto* sidebarHeader = new QFrame(leftShell);
    sidebarHeader->setObjectName("sidebarHeader");
    sidebarHeader->setFixedHeight(48);
    auto* sidebarHeaderLayout = new QVBoxLayout(sidebarHeader);
    sidebarHeaderLayout->setContentsMargins(10, 7, 10, 5);
    sidebarHeaderLayout->setSpacing(0);
    auto* sidebarTitle = new QLabel("控制面板", sidebarHeader);
    sidebarTitle->setObjectName("sidebarTitle");
    auto* sidebarSubtitle = new QLabel("SYSTEM PARAMETERS", sidebarHeader);
    sidebarSubtitle->setObjectName("sidebarSubtitle");
    sidebarHeaderLayout->addWidget(sidebarTitle);
    sidebarHeaderLayout->addWidget(sidebarSubtitle);
    leftLayout->addWidget(sidebarHeader);

    auto* sidebarNavigation = new QWidget(leftShell);
    sidebarNavigation->setObjectName("sidebarNavigation");
    auto* sidebarNavigationLayout = new QVBoxLayout(sidebarNavigation);
    sidebarNavigationLayout->setContentsMargins(0, 0, 0, 0);
    sidebarNavigationLayout->setSpacing(0);

    pathPanel_ = buildPathPanel();
    paramPanel_ = buildParamPanel();
    roiPanel_ = buildRoiPanel();
    controlPanel_ = buildControlPanel();
    actionPanel_ = buildActionPanel();
    pathPanel_->setVisible(false);
    paramPanel_->setVisible(false);
    roiPanel_->setVisible(false);
    controlPanel_->setVisible(false);

    auto* videoSourceButton = buildSidebarNavigationButton("▣  视频源", pathPanel_, sidebarNavigation);
    auto* inferenceButton = buildSidebarNavigationButton("◉  推理参数", paramPanel_, sidebarNavigation);
    auto* roiButton = buildSidebarNavigationButton("⌗  ROI 区域", roiPanel_, sidebarNavigation);
    auto* controlButton = buildSidebarNavigationButton("▥  检测控制", controlPanel_, sidebarNavigation);
    videoSourceButton->setChecked(true);
    pathPanel_->setVisible(true);
    sidebarNavigationLayout->addWidget(videoSourceButton);
    sidebarNavigationLayout->addWidget(inferenceButton);
    sidebarNavigationLayout->addWidget(roiButton);
    sidebarNavigationLayout->addWidget(controlButton);
    leftLayout->addWidget(sidebarNavigation);

    auto* settingsContent = new QWidget(leftShell);
    settingsContent->setObjectName("settingsContent");
    auto* settingsContentLayout = new QVBoxLayout(settingsContent);
    settingsContentLayout->setContentsMargins(6, 5, 6, 5);
    settingsContentLayout->setSpacing(6);
    settingsContentLayout->addWidget(pathPanel_);
    settingsContentLayout->addWidget(paramPanel_);
    settingsContentLayout->addWidget(roiPanel_);
    settingsContentLayout->addWidget(controlPanel_);
    settingsContentLayout->addStretch(1);

    auto* settingsScroll = new QScrollArea(leftShell);
    settingsScroll->setObjectName("settingsScroll");
    settingsScroll->setWidgetResizable(true);
    settingsScroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    settingsScroll->setFrameShape(QFrame::NoFrame);
    settingsScroll->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Expanding);
    settingsScroll->verticalScrollBar()->setSingleStep(28);
    settingsScroll->verticalScrollBar()->setPageStep(160);
    settingsScroll->setWidget(settingsContent);
    leftLayout->addWidget(settingsScroll, 1);
    leftLayout->addWidget(actionPanel_);

    auto* right = new QWidget(root);
    right->setObjectName("monitorWorkspace");
    right->setMinimumWidth(0);
    right->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    auto* rightLayout = new QVBoxLayout(right);
    rightLayout->setContentsMargins(0, 0, 0, 0);
    rightLayout->setSpacing(4);
    rightLayout->setSizeConstraint(QLayout::SetNoConstraint);
    rightLayout->addWidget(buildDashboardPanel());

    auto* monitorPanel = new QFrame(right);
    monitorPanel->setObjectName("monitorPanel");
    auto* monitorLayout = new QVBoxLayout(monitorPanel);
    monitorLayout->setContentsMargins(1, 1, 1, 1);
    monitorLayout->setSpacing(0);
    auto* monitorHeader = new QFrame(monitorPanel);
    monitorHeader->setObjectName("monitorHeader");
    monitorHeader->setFixedHeight(28);
    auto* monitorHeaderLayout = new QHBoxLayout(monitorHeader);
    monitorHeaderLayout->setContentsMargins(10, 0, 10, 0);
    auto* monitorTitle = new QLabel("实时监控画面", monitorHeader);
    monitorTitle->setObjectName("sectionTitle");
    auto* monitorHint = new QLabel("ROI 可视化 · 实时检测", monitorHeader);
    monitorHint->setObjectName("sectionHint");
    monitorHeaderLayout->addWidget(monitorTitle);
    monitorHeaderLayout->addStretch(1);
    monitorHeaderLayout->addWidget(monitorHint);

    previewLabel_ = new RoiPreviewLabel(monitorPanel);
    previewLabel_->setObjectName("videoSurface");
    previewLabel_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    monitorLayout->addWidget(monitorHeader);
    monitorLayout->addWidget(previewLabel_, 1);

    auto* regionPanel = new QFrame(right);
    regionPanel->setObjectName("regionPanel");
    regionPanel->setMinimumHeight(28);
    regionPanel->setMaximumHeight(28);
    regionPanel->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
    auto* regionPanelLayout = new QVBoxLayout(regionPanel);
    regionPanelLayout->setContentsMargins(0, 0, 0, 0);
    regionPanelLayout->setSpacing(0);
    auto* regionHeader = new QFrame(regionPanel);
    regionHeader->setObjectName("regionHeader");
    regionHeader->setFixedHeight(28);
    auto* regionHeaderLayout = new QHBoxLayout(regionHeader);
    regionHeaderLayout->setContentsMargins(10, 0, 6, 0);
    auto* regionTitle = new QLabel("区域统计详情", regionHeader);
    regionTitle->setObjectName("sectionTitle");
    regionHeaderLayout->addWidget(regionTitle);
    regionHeaderLayout->addStretch(1);

    regionDetailsToggleButton_ = new QPushButton("展开区域统计", regionHeader);
    regionDetailsToggleButton_->setObjectName("regionDetailsToggleButton");
    regionDetailsToggleButton_->setCheckable(true);
    regionDetailsToggleButton_->setMaximumWidth(130);
    regionHeaderLayout->addWidget(regionDetailsToggleButton_);

    logToggleButton_ = new QPushButton("展开运行日志", regionHeader);
    logToggleButton_->setObjectName("logToggleButton");
    logToggleButton_->setCheckable(true);
    logToggleButton_->setMaximumWidth(130);
    regionHeaderLayout->addWidget(logToggleButton_);

    regionDetailsContent_ = new QWidget(regionPanel);
    auto* regionDetailsLayout = new QVBoxLayout(regionDetailsContent_);
    regionDetailsLayout->setContentsMargins(0, 0, 0, 0);
    regionDetailsLayout->setSpacing(0);
    regionTable_ = new QTableWidget(0, 6, regionDetailsContent_);
    regionTable_->setHorizontalHeaderLabels({"区域状态", "累计包裹", "区域内", "当前状态", "堵包秒数", "堵包次数"});
    regionTable_->verticalHeader()->setVisible(false);
    regionTable_->horizontalHeader()->setStretchLastSection(true);
    regionTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    regionTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
    regionTable_->setSelectionMode(QAbstractItemView::NoSelection);
    regionTable_->setFocusPolicy(Qt::NoFocus);
    regionTable_->setMinimumHeight(132);
    regionTable_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Expanding);
    regionTable_->verticalHeader()->setDefaultSectionSize(24);
    regionEmptyLabel_ = new QLabel("尚未配置监测区域，请在 ROI 区域绘制并保存。", regionDetailsContent_);
    regionEmptyLabel_->setObjectName("emptyState");
    regionEmptyLabel_->setAlignment(Qt::AlignCenter);
    regionDetailsLayout->addWidget(regionEmptyLabel_);
    regionDetailsLayout->addWidget(regionTable_);
    regionDetailsContent_->setVisible(false);
    regionPanelLayout->addWidget(regionHeader);
    regionPanelLayout->addWidget(regionDetailsContent_);

    logEdit_ = new QPlainTextEdit(right);
    logEdit_->setReadOnly(true);
    logEdit_->setMinimumHeight(80);
    logEdit_->setMaximumHeight(120);
    logEdit_->setVisible(false);
    connect(logToggleButton_, &QPushButton::toggled, this, [this](bool checked) {
        logEdit_->setVisible(checked);
        logToggleButton_->setText(checked ? "收起运行日志" : "展开运行日志");
    });
    connect(regionDetailsToggleButton_, &QPushButton::toggled, this, [this, regionPanel](bool checked) {
        regionDetailsContent_->setVisible(checked);
        regionDetailsToggleButton_->setText(checked ? "收起区域统计" : "展开区域统计");
        regionPanel->setMinimumHeight(checked ? 170 : 28);
        regionPanel->setMaximumHeight(checked ? 220 : 28);
    });

    rightLayout->addWidget(monitorPanel, 1);
    rightLayout->addWidget(regionPanel);
    rightLayout->addWidget(logEdit_);

    splitter->addWidget(leftShell);
    splitter->addWidget(right);
    splitter->setStretchFactor(0, 0);
    splitter->setStretchFactor(1, 1);
    splitter->setSizes({240, 1040});
    connect(splitter, &QSplitter::splitterMoved, this, [this](int position, int) {
        QFont font = settingsPanel_->font();
        font.setPixelSize(qBound(11, position / 26, 14));
        settingsPanel_->setFont(font);
    });
    QTimer::singleShot(0, this, [this]() {
        resizeSidebarToStitchRatio();
    });
    layout->addWidget(splitter, 1);
    setCentralWidget(root);

    setStyleSheet(
        "QWidget{background:#0B1118;color:#F3F7FA;font-family:'Microsoft YaHei UI';}"
        "QFrame#brandBar{background:#111B25;border:1px solid #263746;border-radius:3px;}"
        "QLabel#brandLogo{background:transparent;}"
        "QLabel#brandTitle{background:transparent;color:#F3F7FA;font-size:13px;font-weight:700;letter-spacing:1px;}"
        "QLabel#brandSubtitle{background:transparent;color:#8FA5B8;font-size:9px;}"
        "QLabel#versionBadge{background:#172431;border:1px solid #263746;border-radius:3px;padding:3px 7px;color:#8FA5B8;font-size:9px;}"
        "QLabel#connectionPill{background:#10251F;border:1px solid #245B47;border-radius:3px;padding:3px 8px;color:#36C98F;font-size:9px;}"
        "QLabel#channelStatus,QLabel#runtimeClock{background:#172431;border:1px solid #263746;border-radius:3px;padding:3px 7px;color:#B8C8D4;font-size:9px;}"
        "QLabel#systemStatus{background:#10251F;border:1px solid #245B47;border-radius:3px;padding:3px 8px;color:#36C98F;font-size:10px;font-weight:600;}"
        "QWidget#settingsPanel{background:#151C24;border:1px solid #263746;}"
        "QFrame#sidebarHeader{background:#111820;border-bottom:1px solid #263746;}"
        "QLabel#sidebarTitle{background:transparent;color:#F3F7FA;font-size:12px;font-weight:700;}"
        "QLabel#sidebarSubtitle{background:transparent;color:#708395;font-size:8px;letter-spacing:1px;}"
        "QWidget#sidebarNavigation{background:#151C24;border-bottom:1px solid #263746;}"
        "QPushButton#sidebarNavigationButton{background:#151C24;border:none;border-left:3px solid transparent;border-radius:0;padding:8px 10px;text-align:left;color:#C8D4DE;font-weight:500;}"
        "QPushButton#sidebarNavigationButton:hover{background:#1A2530;color:#F3F7FA;}"
        "QPushButton#sidebarNavigationButton:checked{background:#202B36;border-left:3px solid #2F88F5;color:#F3F7FA;}"
        "QWidget#settingsContent{background:#151C24;}"
        "QWidget#monitorWorkspace{background:#0B1118;}"
        "QFrame#monitorPanel,QFrame#regionPanel{background:#080D13;border:1px solid #263746;border-radius:3px;}"
        "QFrame#monitorHeader{background:#111B25;border-bottom:1px solid #263746;}"
        "QFrame#regionHeader{background:#111B25;border-bottom:1px solid #263746;}"
        "QLabel#sectionTitle{background:transparent;color:#F3F7FA;font-weight:600;}"
        "QLabel#sectionHint{background:transparent;color:#8FA5B8;font-size:9px;}"
        "QLabel#emptyState{background:#0B1118;color:#708395;padding:5px;border-bottom:1px solid #263746;}"
        "QLabel#videoSurface{background:#080D13;border:none;}"
        "QSplitter::handle{background:#172431;}"
        "QSplitter::handle:hover{background:#2F88F5;}"
        "QScrollArea{background:#0B1118;border:none;}"
        "QScrollBar:vertical{background:#0B1118;width:9px;margin:0;border:none;}"
        "QScrollBar::handle:vertical{background:#3A4D5E;min-height:42px;border-radius:4px;}"
        "QScrollBar::handle:vertical:hover{background:#4DA3FF;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:none;border:none;}"
        "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}"
        "QGroupBox{border:1px solid #263746;border-radius:5px;margin-top:12px;padding:8px;color:#8FA5B8;background:#111B25;font-weight:600;}"
        "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;background:#111B25;color:#8FA5B8;}"
        "QLabel{color:#D7E2EA;}"
        "QWidget#dashboardStrip{background:#0B1118;}"
        "QLabel#dashboardTitle{background:transparent;font-size:9px;color:#8FA5B8;}"
        "QLabel#dashboardValue{background:transparent;font-size:18px;font-weight:700;color:#F3F7FA;}"
        "QFrame#dashboardCard{background:#111B25;border:1px solid #263746;border-left:2px solid #2F88F5;border-radius:3px;}"
        "QLineEdit,QPlainTextEdit,QComboBox,QTableWidget{background:#0B1118;border:1px solid #263746;border-radius:4px;padding:6px;color:#F3F7FA;selection-background-color:#2F88F5;gridline-color:#263746;}"
        "QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus{border:1px solid #4DA3FF;}"
        "QHeaderView::section{background:#172431;color:#8FA5B8;border:none;border-right:1px solid #263746;border-bottom:1px solid #263746;padding:6px;font-weight:600;}"
        "QSpinBox,QDoubleSpinBox{background:#0B1118;border:1px solid #263746;border-radius:4px;padding:5px 30px 5px 6px;color:#F3F7FA;selection-background-color:#2F88F5;}"
        "QSpinBox:focus,QDoubleSpinBox:focus{border:1px solid #4DA3FF;}"
        "QSpinBox::up-button,QDoubleSpinBox::up-button{subcontrol-origin:border;subcontrol-position:top right;width:24px;background:#172431;border-left:1px solid #263746;border-bottom:1px solid #263746;}"
        "QSpinBox::down-button,QDoubleSpinBox::down-button{subcontrol-origin:border;subcontrol-position:bottom right;width:24px;background:#172431;border-left:1px solid #263746;border-top:1px solid #263746;}"
        "QSpinBox::up-button:hover,QDoubleSpinBox::up-button:hover,QSpinBox::down-button:hover,QDoubleSpinBox::down-button:hover{background:#21364A;}"
        "QSpinBox::up-arrow,QDoubleSpinBox::up-arrow{width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:7px solid #4DA3FF;}"
        "QSpinBox::down-arrow,QDoubleSpinBox::down-arrow{width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:7px solid #4DA3FF;}"
        "QComboBox::drop-down{background:#172431;border-left:1px solid #263746;width:26px;}"
        "QComboBox::down-arrow{width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:7px solid #4DA3FF;}"
        "QPushButton{background:#172431;border:1px solid #31485B;border-radius:4px;padding:7px;color:#DCE7EE;}"
        "QPushButton:hover{background:#21364A;border-color:#4DA3FF;color:#F3F7FA;}"
        "QPushButton:checked{background:#173B63;border-color:#4DA3FF;color:#F3F7FA;}"
        "QPushButton#primaryButton{background:#2F88F5;border-color:#4DA3FF;color:white;font-weight:700;}"
        "QPushButton#primaryButton:hover{background:#4DA3FF;}"
        "QPushButton#dangerButton{background:#4A2024;border-color:#8D343C;color:#FFDDE0;font-weight:600;}"
        "QPushButton#dangerButton:hover{background:#67282F;border-color:#F25555;}"
        "QPushButton#logToggleButton{padding:3px 8px;color:#4DA3FF;background:transparent;border:none;font-size:9px;}"
        "QPushButton#logToggleButton:hover{background:#172431;border:none;color:#F3F7FA;}"
        "QWidget#actionDock{background:#151C24;border-top:1px solid #263746;}"
        "QPushButton:disabled{background:#121B23;border-color:#26323D;color:#536574;}"
        "QCheckBox{spacing:8px;}"
        "QCheckBox::indicator{width:16px;height:16px;border:1px solid #3A5367;background:#0B1118;border-radius:3px;}"
        "QCheckBox::indicator:checked{background:#2F88F5;border:1px solid #4DA3FF;}"
    );

    flashTimer_ = new QTimer(this);
    flashTimer_->setInterval(500);
    connect(flashTimer_, &QTimer::timeout, this, &MainWindow::toggleAlarmFlash);
    clockTimer_ = new QTimer(this);
    clockTimer_->setInterval(1000);
    connect(clockTimer_, &QTimer::timeout, this, &MainWindow::refreshRuntimeOverview);
    clockTimer_->start();

    connect(previewLabel_, &RoiPreviewLabel::flowRegionChanged, this, [this](
        const QString& regionId,
        const QVector<QPoint>& polygon,
        bool closed
    ) {
        const int index = findRegionIndexById(regionId);
        if (index < 0) {
            return;
        }
        regions_[index].polygon = polygon;
        regions_[index].polygonClosed = closed;
        flowRoiEdit_->setText(::polygonToText(polygon));
        refreshRegionTable();
    });
    connect(previewLabel_, &RoiPreviewLabel::roiChanged, this, [this](RoiPreviewLabel::DrawMode mode, const QString& text) {
        if (mode == RoiPreviewLabel::DrawMode::DetectRoi) {
            detectRoiEdit_->setText(text);
        }
    });

    appendLog("已启动 CVDS 在线包裹流量监测，版本：" + RuntimePaths::versionText());
    appendLog("worker 已就绪：cvds_detector_worker.exe");
    populateClassCombo({});
    loadSettings();
    if (QFileInfo::exists(RuntimePaths::defaultRegionsConfigPath())) {
        try {
            restoreRegionConfigDocument(loadRegionConfigDocument(RuntimePaths::defaultRegionsConfigPath()));
            appendLog("已加载区域配置：regions.json");
        } catch (const std::exception& ex) {
            appendLog("加载区域配置失败：" + QString::fromUtf8(ex.what()));
            QMessageBox::critical(this, "区域配置错误", QString::fromUtf8(ex.what()));
            refreshRegionTable();
        }
    } else {
        ensureDefaultRegion();
        refreshRegionSelectors();
        applyRegionSelection();
        refreshRegionTable();
    }
    previewLabel_->setDetectRoiFromText(detectRoiEdit_->text().trimmed());
    refreshRuntimeOverview();
    appendLog("启动完成：已延迟加载模型类别和视频预览，选择模型或开始检测时再读取。");
}

MainWindow::~MainWindow() {
    saveSettings();
    stopDetection();
    if (modelInspectProcess_ != nullptr && modelInspectProcess_->state() != QProcess::NotRunning) {
        modelInspectProcess_->disconnect(this);
        modelInspectProcess_->kill();
        modelInspectProcess_->waitForFinished(3000);
    }
    if (streamProbeProcess_ != nullptr && streamProbeProcess_->state() != QProcess::NotRunning) {
        streamProbeProcess_->disconnect(this);
        streamProbeProcess_->kill();
        streamProbeProcess_->waitForFinished(3000);
    }
    if (workerThread_ != nullptr) {
        workerThread_->quit();
        workerThread_->wait();
    }
}

void MainWindow::resizeEvent(QResizeEvent* event) {
    QMainWindow::resizeEvent(event);
    QTimer::singleShot(0, this, [this]() {
        resizeSidebarToStitchRatio();
    });
}

void MainWindow::resizeSidebarToStitchRatio() {
    if (mainSplitter_ == nullptr || settingsPanel_ == nullptr || mainSplitter_->width() <= 0) {
        return;
    }
    const int leftWidth = qBound(210, mainSplitter_->width() * 24 / 100, 340);
    mainSplitter_->setSizes({leftWidth, std::max(1, mainSplitter_->width() - leftWidth)});
    QFont font = settingsPanel_->font();
    font.setPixelSize(qBound(11, leftWidth / 26, 14));
    settingsPanel_->setFont(font);
}

void MainWindow::refreshRuntimeOverview() {
    if (clockLabel_ != nullptr) {
        clockLabel_->setText(QDateTime::currentDateTime().toString("yyyy-MM-dd  HH:mm:ss"));
    }
    if (sourceStatusLabel_ == nullptr || channelStatusLabel_ == nullptr) {
        return;
    }

    const bool streamMode = sourceModeCombo_ != nullptr
        && sourceModeCombo_->currentData().toString() == "stream";
    if (streamMode) {
        const QString host = hikIpEdit_ == nullptr ? QString() : hikIpEdit_->text().trimmed();
        sourceStatusLabel_->setText(host.isEmpty() ? "●  视频流未配置" : "●  " + host + " · 在线监测");
        const int channel = hikChannelSpin_ == nullptr ? 0 : hikChannelSpin_->value();
        const QString streamName = hikStreamCombo_ == nullptr ? QString() : hikStreamCombo_->currentText();
        channelStatusLabel_->setText(channel > 0 ? QString("通道 %1 · %2").arg(channel).arg(streamName) : "通道 --");
        return;
    }

    const QString source = privatePath(sourceEdit_);
    sourceStatusLabel_->setText(source.isEmpty() ? "●  未选择视频源" : "●  " + QFileInfo(source).fileName());
    channelStatusLabel_->setText("本地文件");
}

QWidget* MainWindow::buildPathPanel() {
    auto* box = new QGroupBox("视频源");
    auto* rootLayout = new QVBoxLayout(box);
    auto* layout = new QGridLayout();
    layout->setColumnStretch(1, 1);
    sourceEdit_ = new QLineEdit(box);
    sourceEdit_->setReadOnly(true);
    setPrivatePath(sourceEdit_, {});
    sourceModeCombo_ = new ScrollSafeComboBox(box);
    sourceModeCombo_->addItem("本地文件", "file");
    sourceModeCombo_->addItem("视频流", "stream");
    layout->addWidget(new QLabel("来源类型", box), 0, 0);
    layout->addWidget(sourceModeCombo_, 0, 1, 1, 2);

    auto* sourceLabel = new QLabel("本地文件", box);
    auto* sourceButton = new QPushButton("选择", box);
    sourceButton->setMaximumWidth(54);
    connect(sourceButton, &QPushButton::clicked, this, &MainWindow::browseSource);
    layout->addWidget(sourceLabel, 1, 0);
    layout->addWidget(sourceEdit_, 1, 1);
    layout->addWidget(sourceButton, 1, 2);
    rootLayout->addLayout(layout);

    streamSettingsWidget_ = new QWidget(box);
    auto* streamLayout = new QGridLayout(streamSettingsWidget_);
    streamLayout->setContentsMargins(0, 4, 0, 0);
    streamLayout->setColumnStretch(1, 1);
    hikIpEdit_ = new QLineEdit(box);
    hikUserEdit_ = new QLineEdit("admin", box);
    hikPasswordEdit_ = new QLineEdit(box);
    hikChannelSpin_ = new ScrollSafeSpinBox(box);
    hikRtspPortSpin_ = new ScrollSafeSpinBox(box);
    hikStreamCombo_ = new ScrollSafeComboBox(box);
    hikTransportCombo_ = new ScrollSafeComboBox(box);
    hikPasswordEdit_->setEchoMode(QLineEdit::Password);
    hikIpEdit_->setPlaceholderText("192.168.1.64");
    hikPasswordEdit_->setPlaceholderText("海康相机密码");
    hikChannelSpin_->setRange(1, 999);
    hikChannelSpin_->setValue(1);
    hikRtspPortSpin_->setRange(1, 65535);
    hikRtspPortSpin_->setValue(554);
    hikStreamCombo_->addItem("主码流", 1);
    hikStreamCombo_->addItem("子码流", 2);
    hikTransportCombo_->addItem("TCP", "tcp");
    hikTransportCombo_->addItem("UDP", "udp");

    streamLayout->addWidget(new QLabel("海康设备", box), 0, 0);
    streamLayout->addWidget(hikIpEdit_, 0, 1);
    streamLayout->addWidget(hikRtspPortSpin_, 0, 2);
    streamLayout->addWidget(new QLabel("登录账号", box), 1, 0);
    auto* hikAuthLayout = new QHBoxLayout();
    hikAuthLayout->addWidget(hikUserEdit_);
    hikAuthLayout->addWidget(hikPasswordEdit_);
    streamLayout->addLayout(hikAuthLayout, 1, 1, 1, 2);
    streamLayout->addWidget(new QLabel("通道/码流", box), 2, 0);
    auto* channelLayout = new QHBoxLayout();
    channelLayout->addWidget(hikChannelSpin_);
    channelLayout->addWidget(hikStreamCombo_);
    streamLayout->addLayout(channelLayout, 2, 1, 1, 2);
    streamLayout->addWidget(new QLabel("传输协议", box), 3, 0);
    streamLayout->addWidget(hikTransportCombo_, 3, 1, 1, 2);
    auto* streamButtons = new QHBoxLayout();
    auto* hikButton = new QPushButton("应用视频流", box);
    auto* testButton = new QPushButton("测试连接", box);
    connect(hikButton, &QPushButton::clicked, this, &MainWindow::applyHikvisionStream);
    connect(testButton, &QPushButton::clicked, this, &MainWindow::testVideoStream);
    streamButtons->addWidget(hikButton);
    streamButtons->addWidget(testButton);
    streamLayout->addLayout(streamButtons, 4, 0, 1, 3);
    rootLayout->addWidget(streamSettingsWidget_);

    connect(
        sourceModeCombo_,
        qOverload<int>(&QComboBox::currentIndexChanged),
        this,
        [this, sourceLabel, sourceButton](int) {
        const bool streamMode = sourceModeCombo_->currentData().toString() == "stream";
        sourceLabel->setVisible(!streamMode);
        sourceEdit_->setVisible(!streamMode);
        sourceButton->setVisible(!streamMode);
        streamSettingsWidget_->setVisible(streamMode);
        refreshRuntimeOverview();
        }
    );
    streamSettingsWidget_->setVisible(false);

    return box;
}

QWidget* MainWindow::buildParamPanel() {
    auto* box = new QGroupBox("推理参数");
    auto* form = new QFormLayout(box);
    modelEdit_ = new QLineEdit(box);
    modelEdit_->setReadOnly(true);
    setPrivatePath(modelEdit_, findDefaultModelPath());
    auto* modelButtons = new QWidget(box);
    auto* modelButtonLayout = new QHBoxLayout(modelButtons);
    modelButtonLayout->setContentsMargins(0, 0, 0, 0);
    auto* modelFileButton = new QPushButton("模型文件", modelButtons);
    auto* openVinoButton = new QPushButton("OpenVINO目录", modelButtons);
    connect(modelFileButton, &QPushButton::clicked, this, &MainWindow::browseModel);
    connect(openVinoButton, &QPushButton::clicked, this, &MainWindow::browseOpenVinoDirectory);
    modelButtonLayout->addWidget(modelFileButton);
    modelButtonLayout->addWidget(openVinoButton);
    classCombo_ = new ScrollSafeComboBox(box);
    classCombo_->addItem("全部类别", -1);
    deviceCombo_ = new ScrollSafeComboBox(box);
    deviceCombo_->addItem("自动", "auto");
    deviceCombo_->addItem("CPU", "cpu");
    deviceCombo_->addItem("NVIDIA GPU", "0");
    deviceCombo_->addItem("Intel GPU", "intel:gpu");
    deviceCombo_->addItem("Intel NPU", "intel:npu");
    inputSizeSpin_ = new ScrollSafeSpinBox(box);
    inputSizeSpin_->setRange(160, 1536);
    inputSizeSpin_->setSingleStep(32);
    inputSizeSpin_->setValue(960);
    videoFpsSpin_ = new ScrollSafeSpinBox(box);
    videoFpsSpin_->setRange(1, 120);
    videoFpsSpin_->setSingleStep(5);
    videoFpsSpin_->setValue(60);
    confidenceSpin_ = new ScrollSafeDoubleSpinBox(box);
    confidenceSpin_->setRange(0.01, 0.99);
    confidenceSpin_->setSingleStep(0.05);
    confidenceSpin_->setValue(0.25);
    iouSpin_ = new ScrollSafeDoubleSpinBox(box);
    iouSpin_->setRange(0.01, 0.99);
    iouSpin_->setSingleStep(0.05);
    iouSpin_->setValue(0.45);

    form->addRow("视觉模型", modelEdit_);
    form->addRow("选择方式", modelButtons);
    form->addRow("类别", classCombo_);
    form->addRow("执行设备", deviceCombo_);
    form->addRow("输入尺寸", inputSizeSpin_);
    form->addRow("预览FPS", videoFpsSpin_);
    form->addRow("置信度", confidenceSpin_);
    form->addRow("NMS IoU", iouSpin_);
    return box;
}

QWidget* MainWindow::buildRoiPanel() {
    auto* box = new QGroupBox("流量监测");
    auto* layout = new QVBoxLayout(box);
    auto* form = new QFormLayout();

    regionCombo_ = new ScrollSafeComboBox(box);
    totalCountRegionCombo_ = new ScrollSafeComboBox(box);
    regionNameEdit_ = new QLineEdit(box);
    flowRoiEdit_ = new QLineEdit(box);
    detectRoiEdit_ = new QLineEdit(box);
    countEnabledCheck_ = new QCheckBox("参与累计", box);
    jamEnabledCheck_ = new QCheckBox("启用堵包", box);
    jamSecondsSpin_ = new ScrollSafeSpinBox(box);
    jamSecondsSpin_->setRange(1, 600);
    jamSecondsSpin_->setValue(5);
    flowRoiEdit_->setPlaceholderText("左键加点，右键完成，Esc/Ctrl+Z撤回");
    detectRoiEdit_->setPlaceholderText("可选，只在该多边形区域检测");

    form->addRow("当前区域", regionCombo_);
    form->addRow("区域名称", regionNameEdit_);
    form->addRow("当前区域ROI", flowRoiEdit_);
    form->addRow("检测区域", detectRoiEdit_);
    form->addRow("主统计区域", totalCountRegionCombo_);
    form->addRow("堵包判定秒", jamSecondsSpin_);

    auto* switchLayout = new QHBoxLayout();
    switchLayout->addWidget(countEnabledCheck_);
    switchLayout->addWidget(jamEnabledCheck_);
    switchLayout->addStretch(1);

    auto* help = new QLabel("ROI绘制：左键逐点绘制，多边形至少3点，右键完成，Esc或Ctrl+Z撤回上一个点。", box);
    help->setWordWrap(true);

    auto* regionButtons = new QHBoxLayout();
    auto* addButton = new QPushButton("新增区域", box);
    auto* renameButton = new QPushButton("重命名区域", box);
    auto* deleteButton = new QPushButton("删除区域", box);
    regionButtons->addWidget(addButton);
    regionButtons->addWidget(renameButton);
    regionButtons->addWidget(deleteButton);

    auto* drawButtons = new QGridLayout();
    drawFlowRoiButton_ = new QPushButton("绘制流量ROI", box);
    drawDetectRoiButton_ = new QPushButton("绘制检测区域", box);
    auto* undoButton = new QPushButton("撤回ROI点", box);
    auto* clearButton = new QPushButton("清空当前ROI", box);
    drawFlowRoiButton_->setCheckable(true);
    drawDetectRoiButton_->setCheckable(true);
    drawFlowRoiButton_->setChecked(true);
    drawButtons->addWidget(drawFlowRoiButton_, 0, 0);
    drawButtons->addWidget(drawDetectRoiButton_, 0, 1);
    drawButtons->addWidget(undoButton, 1, 0);
    drawButtons->addWidget(clearButton, 1, 1);

    auto* configButtons = new QHBoxLayout();
    auto* saveButton = new QPushButton("保存区域配置", box);
    auto* loadButton = new QPushButton("加载区域配置", box);
    configButtons->addWidget(saveButton);
    configButtons->addWidget(loadButton);

    layout->addLayout(form);
    layout->addLayout(switchLayout);
    layout->addWidget(help);
    layout->addLayout(regionButtons);
    layout->addLayout(drawButtons);
    layout->addLayout(configButtons);

    connect(regionCombo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [this]() {
        applyRegionSelection();
    });
    connect(totalCountRegionCombo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [this]() {
        const QString selectedId = totalCountRegionCombo_->currentData().toString();
        const int selectedIndex = findRegionIndexById(selectedId);
        if (selectedIndex >= 0 && !regions_[selectedIndex].countEnabled) {
            QMessageBox::warning(this, "主统计区域错误", "主统计区域必须参与累计。");
            const QSignalBlocker blocker(totalCountRegionCombo_);
            totalCountRegionCombo_->setCurrentIndex(totalCountRegionCombo_->findData(totalCountRegionId_));
            return;
        }
        totalCountRegionId_ = selectedId;
        refreshRegionTable();
    });
    connect(regionNameEdit_, &QLineEdit::editingFinished, this, &MainWindow::renameCurrentRegion);
    connect(addButton, &QPushButton::clicked, this, &MainWindow::addRegion);
    connect(renameButton, &QPushButton::clicked, this, &MainWindow::renameCurrentRegion);
    connect(deleteButton, &QPushButton::clicked, this, &MainWindow::deleteCurrentRegion);
    connect(saveButton, &QPushButton::clicked, this, &MainWindow::saveRegionConfig);
    connect(loadButton, &QPushButton::clicked, this, &MainWindow::loadRegionConfig);
    connect(drawFlowRoiButton_, &QPushButton::clicked, this, [this]() {
        setRoiDrawMode(RoiPreviewLabel::DrawMode::FlowRoi);
    });
    connect(drawDetectRoiButton_, &QPushButton::clicked, this, [this]() {
        setRoiDrawMode(RoiPreviewLabel::DrawMode::DetectRoi);
    });
    connect(undoButton, &QPushButton::clicked, this, [this]() {
        previewLabel_->undoCurrentPoint();
    });
    connect(clearButton, &QPushButton::clicked, this, [this]() {
        previewLabel_->clearCurrentRoi();
    });
    connect(flowRoiEdit_, &QLineEdit::editingFinished, this, [this]() {
        const int index = findRegionIndexById(currentRegionId_);
        if (index < 0) {
            return;
        }
        try {
            regions_[index].polygon = parseEditablePolygonText(flowRoiEdit_->text(), "当前区域 ROI", true);
            regions_[index].polygonClosed = regions_[index].polygon.size() >= 3;
            previewLabel_->setFlowRegions(regions_);
            previewLabel_->setActiveRegionId(currentRegionId_);
            refreshRegionTable();
        } catch (const std::exception& ex) {
            QMessageBox::warning(this, "区域配置错误", QString::fromUtf8(ex.what()));
            flowRoiEdit_->setText(::polygonToText(regions_[index].polygon));
        }
    });
    connect(detectRoiEdit_, &QLineEdit::editingFinished, this, &MainWindow::updateDetectRoiFromEditor);
    connect(countEnabledCheck_, &QCheckBox::toggled, this, [this](bool checked) {
        const int index = findRegionIndexById(currentRegionId_);
        if (index >= 0) {
            if (totalCountRegionId_ == currentRegionId_ && !checked) {
                QMessageBox::warning(this, "主统计区域错误", "主统计区域必须参与累计。");
                const QSignalBlocker blocker(countEnabledCheck_);
                countEnabledCheck_->setChecked(true);
                return;
            }
            regions_[index].countEnabled = checked;
            refreshRegionTable();
        }
    });
    connect(jamEnabledCheck_, &QCheckBox::toggled, this, [this](bool checked) {
        const int index = findRegionIndexById(currentRegionId_);
        if (index >= 0) {
            regions_[index].jamEnabled = checked;
            refreshRegionTable();
        }
    });
    connect(jamSecondsSpin_, qOverload<int>(&QSpinBox::valueChanged), this, [this](int value) {
        const int index = findRegionIndexById(currentRegionId_);
        if (index >= 0) {
            regions_[index].jamSeconds = value;
        }
    });
    return box;
}

QWidget* MainWindow::buildActionPanel() {
    auto* box = new QWidget();
    box->setObjectName("actionDock");
    auto* layout = new QVBoxLayout(box);
    layout->setContentsMargins(6, 6, 6, 6);
    layout->setSpacing(4);
    startButton_ = new QPushButton("开始检测", box);
    stopButton_ = new QPushButton("停止检测", box);
    startButton_->setObjectName("primaryButton");
    stopButton_->setObjectName("dangerButton");
    stopButton_->setEnabled(false);
    connect(startButton_, &QPushButton::clicked, this, &MainWindow::startDetection);
    connect(stopButton_, &QPushButton::clicked, this, &MainWindow::stopDetection);
    layout->addWidget(startButton_);
    layout->addWidget(stopButton_);
    return box;
}

QWidget* MainWindow::buildControlPanel() {
    auto* box = new QGroupBox("检测控制");
    auto* layout = new QFormLayout(box);
    outputEdit_ = new QLineEdit(box);
    outputEdit_->setReadOnly(true);
    setPrivatePath(outputEdit_, RuntimePaths::defaultOutputDir());
    auto* outputButton = new QPushButton("选择输出目录", box);
    connect(outputButton, &QPushButton::clicked, this, &MainWindow::browseOutput);
    diagnoseButton_ = new QPushButton("环境自检", box);
    connect(diagnoseButton_, &QPushButton::clicked, this, &MainWindow::runEnvironmentDiagnose);
    layout->addRow("输出目录", outputEdit_);
    layout->addRow(QString(), outputButton);
    layout->addRow(QString(), diagnoseButton_);
    return box;
}

QPushButton* MainWindow::buildSidebarNavigationButton(
    const QString& text,
    QWidget* panel,
    QWidget* parent
) {
    auto* button = new QPushButton(text, parent);
    button->setObjectName("sidebarNavigationButton");
    button->setCheckable(true);
    button->setAutoExclusive(false);
    sidebarButtons_.push_back(button);
    connect(button, &QPushButton::clicked, this, [this, panel, button]() {
        setSidebarPanelVisible(panel, button);
    });
    return button;
}

void MainWindow::setSidebarPanelVisible(QWidget* panel, QPushButton* button) {
    const bool shouldShow = panel != nullptr && !panel->isVisible();
    for (QPushButton* navigationButton : sidebarButtons_) {
        navigationButton->setChecked(navigationButton == button);
    }
    for (QWidget* settingsPanel : {pathPanel_, paramPanel_, roiPanel_, controlPanel_}) {
        if (settingsPanel != nullptr) {
            settingsPanel->setVisible(shouldShow && settingsPanel == panel);
        }
    }
    if (panel == nullptr && startButton_ != nullptr) {
        startButton_->setFocus(Qt::OtherFocusReason);
    }
}

QWidget* MainWindow::buildDashboardPanel() {
    auto* box = new QWidget();
    box->setObjectName("dashboardStrip");
    box->setFixedHeight(56);
    box->setMinimumWidth(0);
    box->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
    auto* layout = new QHBoxLayout(box);
    layout->setSizeConstraint(QLayout::SetNoConstraint);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(4);

    auto buildCard = [box](const QString& title, QLabel** valueLabel) {
        auto* card = new QFrame(box);
        card->setObjectName("dashboardCard");
        card->setMinimumWidth(0);
        card->setFixedHeight(56);
        card->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        auto* cardLayout = new QHBoxLayout(card);
        cardLayout->setSizeConstraint(QLayout::SetNoConstraint);
        cardLayout->setContentsMargins(9, 3, 9, 3);
        cardLayout->setSpacing(5);
        auto* titleLabel = new QLabel(title, card);
        titleLabel->setObjectName("dashboardTitle");
        titleLabel->setMinimumWidth(0);
        titleLabel->setSizePolicy(QSizePolicy::Minimum, QSizePolicy::Preferred);
        *valueLabel = new QLabel("0", card);
        (*valueLabel)->setObjectName("dashboardValue");
        (*valueLabel)->setMinimumWidth(0);
        (*valueLabel)->setAlignment(Qt::AlignRight | Qt::AlignVCenter);
        (*valueLabel)->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);
        cardLayout->addWidget(titleLabel);
        cardLayout->addStretch(1);
        cardLayout->addWidget(*valueLabel);
        return card;
    };

    layout->addWidget(buildCard("累计包裹", &kpiTotalCountValueLabel_), 1);
    layout->addWidget(buildCard("当前状态", &kpiStatusValueLabel_), 1);
    layout->addWidget(buildCard("区域内包裹", &kpiInsideCountValueLabel_), 1);
    layout->addWidget(buildCard("堵包次数", &kpiJamCountValueLabel_), 1);
    return box;
}

QString MainWindow::buildHikvisionRtsp() const {
    QUrl url;
    url.setScheme("rtsp");
    url.setHost(hikIpEdit_->text().trimmed());
    url.setPort(hikRtspPortSpin_->value());
    url.setUserName(hikUserEdit_->text().trimmed());
    url.setPassword(hikPasswordEdit_->text());
    const int streamId = hikChannelSpin_->value() * 100 + hikStreamCombo_->currentData().toInt();
    url.setPath("/Streaming/Channels/" + QString::number(streamId));
    return url.toString(QUrl::FullyEncoded);
}

void MainWindow::loadSettings() {
    QSettings settings;
    const QString savedModel = settings.value("lastModelPath", privatePath(modelEdit_)).toString();
    setPrivatePath(modelEdit_, QFileInfo::exists(savedModel) ? savedModel : findDefaultModelPath());
    setPrivatePath(
        sourceEdit_,
        sourcePathForSettings(settings.value("lastSourcePath", privatePath(sourceEdit_)).toString())
    );
    const QString savedOutput = settings.value("lastOutputDir", privatePath(outputEdit_)).toString().trimmed();
    setPrivatePath(outputEdit_, savedOutput.isEmpty() ? RuntimePaths::defaultOutputDir() : savedOutput);
    detectRoiEdit_->setText(settings.value("lastDetectRoi", detectRoiEdit_->text()).toString());
    hikIpEdit_->setText(settings.value("hikvisionIp", hikIpEdit_->text()).toString());
    hikUserEdit_->setText(settings.value("hikvisionUser", hikUserEdit_->text()).toString());
    settings.remove("hikvisionPassword");
    hikPasswordEdit_->clear();
    hikChannelSpin_->setValue(settings.value("hikvisionChannel", hikChannelSpin_->value()).toInt());
    hikRtspPortSpin_->setValue(settings.value("hikvisionRtspPort", hikRtspPortSpin_->value()).toInt());
    const int streamIndex = hikStreamCombo_->findData(settings.value("hikvisionStream", 1).toInt());
    hikStreamCombo_->setCurrentIndex(streamIndex >= 0 ? streamIndex : 0);
    const int transportIndex = hikTransportCombo_->findData(settings.value("hikvisionTransport", "tcp").toString());
    hikTransportCombo_->setCurrentIndex(transportIndex >= 0 ? transportIndex : 0);
    const int sourceModeIndex = sourceModeCombo_->findData(settings.value("sourceMode", "file").toString());
    sourceModeCombo_->setCurrentIndex(sourceModeIndex >= 0 ? sourceModeIndex : 0);
    streamSettingsWidget_->setVisible(sourceModeCombo_->currentData().toString() == "stream");
    inputSizeSpin_->setValue(settings.value("inputSize", inputSizeSpin_->value()).toInt());
    videoFpsSpin_->setValue(settings.value("previewFps", videoFpsSpin_->value()).toInt());
    confidenceSpin_->setValue(settings.value("confidence", confidenceSpin_->value()).toDouble());
    iouSpin_->setValue(settings.value("iou", iouSpin_->value()).toDouble());
    const QString savedDevice = settings.value("deviceMode", "auto").toString();
    const int deviceIndex = deviceCombo_->findData(savedDevice);
    deviceCombo_->setCurrentIndex(deviceIndex >= 0 ? deviceIndex : 0);
}

void MainWindow::saveSettings() const {
    QSettings settings;
    settings.setValue("lastModelPath", privatePath(modelEdit_));
    settings.setValue("lastSourcePath", sourcePathForSettings(privatePath(sourceEdit_)));
    settings.setValue("lastOutputDir", privatePath(outputEdit_));
    settings.setValue("lastDetectRoi", detectRoiEdit_->text().trimmed());
    settings.setValue("hikvisionIp", hikIpEdit_->text().trimmed());
    settings.setValue("hikvisionUser", hikUserEdit_->text().trimmed());
    settings.remove("hikvisionPassword");
    settings.setValue("hikvisionChannel", hikChannelSpin_->value());
    settings.setValue("hikvisionRtspPort", hikRtspPortSpin_->value());
    settings.setValue("hikvisionStream", hikStreamCombo_->currentData().toInt());
    settings.setValue("hikvisionTransport", hikTransportCombo_->currentData().toString());
    settings.setValue("sourceMode", sourceModeCombo_->currentData().toString());
    settings.setValue("inputSize", inputSizeSpin_->value());
    settings.setValue("previewFps", videoFpsSpin_->value());
    settings.setValue("confidence", confidenceSpin_->value());
    settings.setValue("iou", iouSpin_->value());
    settings.setValue("deviceMode", deviceCombo_->currentData().toString());
}

void MainWindow::populateClassCombo(const QStringList& labels) {
    const int previousClassId = classCombo_->currentData().toInt();
    classCombo_->clear();
    classCombo_->addItem("全部类别", -1);
    for (int i = 0; i < labels.size(); ++i) {
        classCombo_->addItem(labels[i], i);
    }
    const int restoredIndex = classCombo_->findData(previousClassId);
    classCombo_->setCurrentIndex(restoredIndex >= 0 ? restoredIndex : 0);
}

void MainWindow::setRoiDrawMode(RoiPreviewLabel::DrawMode mode) {
    previewLabel_->setDrawMode(mode);
    drawFlowRoiButton_->setChecked(mode == RoiPreviewLabel::DrawMode::FlowRoi);
    drawDetectRoiButton_->setChecked(mode == RoiPreviewLabel::DrawMode::DetectRoi);
}

void MainWindow::ensureDefaultRegion() {
    if (!regions_.isEmpty()) {
        return;
    }
    RegionConfig region;
    region.id = "main_region";
    region.name = "主统计区域";
    region.priority = 1;
    regions_.push_back(region);
    totalCountRegionId_ = region.id;
    currentRegionId_ = region.id;
}

QString MainWindow::nextRegionId() const {
    for (int i = 1; ; ++i) {
        const QString candidate = QString("region_%1").arg(i);
        if (findRegionIndexById(candidate) < 0) {
            return candidate;
        }
    }
}

int MainWindow::findRegionIndexById(const QString& regionId) const {
    for (int i = 0; i < regions_.size(); ++i) {
        if (regions_[i].id == regionId) {
            return i;
        }
    }
    return -1;
}

void MainWindow::refreshRegionSelectors() {
    ensureDefaultRegion();
    if (currentRegionId_.trimmed().isEmpty() || findRegionIndexById(currentRegionId_) < 0) {
        currentRegionId_ = regions_.first().id;
    }
    if (totalCountRegionId_.trimmed().isEmpty() || findRegionIndexById(totalCountRegionId_) < 0) {
        totalCountRegionId_ = regions_.first().id;
    }

    {
        const QSignalBlocker comboBlocker(regionCombo_);
        regionCombo_->clear();
        for (const RegionConfig& region : regions_) {
            regionCombo_->addItem(region.name, region.id);
        }
        const int currentIndex = regionCombo_->findData(currentRegionId_);
        regionCombo_->setCurrentIndex(currentIndex >= 0 ? currentIndex : 0);
    }
    {
        const QSignalBlocker totalBlocker(totalCountRegionCombo_);
        totalCountRegionCombo_->clear();
        for (const RegionConfig& region : regions_) {
            totalCountRegionCombo_->addItem(region.name, region.id);
        }
        const int totalIndex = totalCountRegionCombo_->findData(totalCountRegionId_);
        totalCountRegionCombo_->setCurrentIndex(totalIndex >= 0 ? totalIndex : 0);
    }

    previewLabel_->setFlowRegions(regions_);
    previewLabel_->setActiveRegionId(currentRegionId_);
}

void MainWindow::syncCurrentRegionEditors() {
    const int index = findRegionIndexById(currentRegionId_);
    if (index < 0) {
        return;
    }
    const RegionConfig& region = regions_[index];
    const QSignalBlocker nameBlocker(regionNameEdit_);
    const QSignalBlocker roiBlocker(flowRoiEdit_);
    const QSignalBlocker countBlocker(countEnabledCheck_);
    const QSignalBlocker jamBlocker(jamEnabledCheck_);
    const QSignalBlocker secondsBlocker(jamSecondsSpin_);
    regionNameEdit_->setText(region.name);
    flowRoiEdit_->setText(::polygonToText(region.polygon));
    countEnabledCheck_->setChecked(region.countEnabled);
    jamEnabledCheck_->setChecked(region.jamEnabled);
    jamSecondsSpin_->setValue(region.jamSeconds);
}

void MainWindow::applyRegionSelection() {
    const QString selectedId = regionCombo_->currentData().toString();
    if (!selectedId.trimmed().isEmpty()) {
        currentRegionId_ = selectedId;
    }
    previewLabel_->setActiveRegionId(currentRegionId_);
    syncCurrentRegionEditors();
    refreshRegionTable();
}

void MainWindow::refreshRegionTable() {
    if (regionTable_ == nullptr) {
        return;
    }
    regionTable_->setRowCount(regions_.size());
    bool hasConfiguredRegion = false;
    for (const RegionConfig& region : regions_) {
        if (region.polygonClosed && region.polygon.size() >= 3) {
            hasConfiguredRegion = true;
            break;
        }
    }
    if (regionEmptyLabel_ != nullptr) {
        regionEmptyLabel_->setVisible(!hasConfiguredRegion);
    }
    QStringList jamIds;
    int insideSum = 0;
    int jamSum = 0;
    for (const RegionRuntimeState& state : regionRuntimeStates_) {
        insideSum += state.insideCount;
        jamSum += state.jamCount;
        if (state.jamActive) {
            jamIds.push_back(state.id);
        }
    }
    if (dashboardInsideCount_ <= 0) {
        dashboardInsideCount_ = insideSum;
    }
    if (dashboardJamCount_ <= 0) {
        dashboardJamCount_ = jamSum;
    }

    for (int row = 0; row < regions_.size(); ++row) {
        const RegionConfig& region = regions_[row];
        RegionRuntimeState state = buildFallbackState(region);
        for (const RegionRuntimeState& item : regionRuntimeStates_) {
            if (item.id == region.id) {
                state = item;
                break;
            }
        }
        if (state.name.trimmed().isEmpty()) {
            state.name = region.name;
        }

        const QString statusText = regionStatusText(state, workerThread_ != nullptr);
        const QString regionText = region.id == totalCountRegionId_
            ? region.name + "（主统计区域）"
            : region.name;
        const QStringList values = {
            regionText,
            QString::number(state.flowCount),
            QString::number(state.insideCount),
            statusText,
            QString::number(state.jamActive ? state.staleSeconds : 0.0, 'f', 1),
            QString::number(state.jamCount),
        };

        for (int column = 0; column < values.size(); ++column) {
            QTableWidgetItem* item = regionTable_->item(row, column);
            if (item == nullptr) {
                item = new QTableWidgetItem();
                regionTable_->setItem(row, column, item);
            }
            item->setText(values[column]);
            if (state.jamActive && dashboardFlashVisible_) {
                item->setBackground(QColor("#4A2024"));
            } else if (region.id == currentRegionId_) {
                item->setBackground(QColor("#172431"));
            } else {
                item->setBackground(QColor("#0B1118"));
            }
        }
    }

    previewLabel_->setJamRegionIds(jamIds);
    previewLabel_->setAlertFlashVisible(dashboardFlashVisible_);
    kpiTotalCountValueLabel_->setText(QString::number(dashboardTotalCount_));
    kpiStatusValueLabel_->setText(dashboardStatusText_);
    kpiInsideCountValueLabel_->setText(QString::number(dashboardInsideCount_));
    kpiJamCountValueLabel_->setText(QString::number(dashboardJamCount_));
    if (dashboardJamActive_ && dashboardFlashVisible_) {
        kpiStatusValueLabel_->setStyleSheet("color:#F25555;font-size:18px;font-weight:700;");
    } else {
        kpiStatusValueLabel_->setStyleSheet("color:#36C98F;font-size:18px;font-weight:700;");
    }
    if (systemStatusLabel_ != nullptr) {
        if (dashboardJamActive_) {
            systemStatusLabel_->setText("●  堵包告警");
            systemStatusLabel_->setStyleSheet(
                "background:#35191C;border:1px solid #8D343C;border-radius:3px;"
                "padding:3px 8px;color:#F25555;font-size:10px;font-weight:600;"
            );
        } else if (workerThread_ != nullptr) {
            systemStatusLabel_->setText("●  正在监测");
            systemStatusLabel_->setStyleSheet(
                "background:#10251F;border:1px solid #245B47;border-radius:3px;"
                "padding:3px 8px;color:#36C98F;font-size:10px;font-weight:600;"
            );
        } else {
            systemStatusLabel_->setText("●  系统就绪");
            systemStatusLabel_->setStyleSheet({});
        }
    }
}

RegionConfigDocument MainWindow::buildRegionConfigDocument() const {
    RegionConfigDocument document;
    document.version = 1;
    document.totalCountRegionId = totalCountRegionId_;
    document.regions = regions_;
    return regionConfigDocumentFromJson(regionConfigDocumentToJson(document));
}

void MainWindow::restoreRegionConfigDocument(const RegionConfigDocument& document) {
    setDashboardAlarmActive(false);
    regionRuntimeStates_.clear();
    dashboardTotalCount_ = 0;
    dashboardInsideCount_ = 0;
    dashboardJamCount_ = 0;
    dashboardStatusText_ = "待机";
    regions_ = document.regions;
    totalCountRegionId_ = document.totalCountRegionId;
    currentRegionId_ = document.regions.isEmpty() ? QString() : document.regions.first().id;
    refreshRegionSelectors();
    applyRegionSelection();
    refreshRegionTable();
}

QVector<QPoint> MainWindow::parseEditablePolygonText(const QString& text, const QString& label, bool allowEmpty) const {
    return polygonFromText(text, label, allowEmpty);
}

void MainWindow::updateDetectRoiFromEditor() {
    try {
        const QVector<QPoint> detectPolygon = parseEditablePolygonText(detectRoiEdit_->text(), "检测 ROI", true);
        detectRoiEdit_->setText(::polygonToText(detectPolygon));
        previewLabel_->setDetectRoiFromText(detectRoiEdit_->text());
    } catch (const std::exception& ex) {
        QMessageBox::warning(this, "区域配置错误", QString::fromUtf8(ex.what()));
        detectRoiEdit_->setText(previewLabel_->detectRoiText());
    }
}

void MainWindow::browseModel() {
    const QString path = QFileDialog::getOpenFileName(
        this,
        "选择视觉模型",
        privatePath(modelEdit_),
        "视觉模型 (*.pt *.onnx *.xml)"
    );
    if (!path.isEmpty()) {
        setPrivatePath(modelEdit_, path, true);
        refreshModelMetadata();
        saveSettings();
    }
}

void MainWindow::browseOpenVinoDirectory() {
    const QString path = QFileDialog::getExistingDirectory(
        this,
        "选择 OpenVINO 模型目录",
        privatePath(modelEdit_)
    );
    if (!path.isEmpty()) {
        setPrivatePath(modelEdit_, path, true);
        refreshModelMetadata();
        saveSettings();
    }
}

void MainWindow::browseSource() {
    const QString path = QFileDialog::getOpenFileName(
        this,
        "选择视频源",
        privatePath(sourceEdit_),
        "Video (*.mp4 *.avi *.mkv *.mov);;All files (*.*)"
    );
    if (!path.isEmpty()) {
        sourceModeCombo_->setCurrentIndex(sourceModeCombo_->findData("file"));
        setPrivatePath(sourceEdit_, path, true);
        loadVideoPreviewFrame();
        refreshRuntimeOverview();
        saveSettings();
    }
}

void MainWindow::applyHikvisionStream() {
    if (hikIpEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少海康地址", "请先填写海康相机 IP 地址。");
        return;
    }
    sourceModeCombo_->setCurrentIndex(sourceModeCombo_->findData("stream"));
    setPrivatePath(sourceEdit_, buildHikvisionRtsp());
    refreshRuntimeOverview();
    saveSettings();
    appendLog("已应用海康视频流配置。");
}

void MainWindow::testVideoStream() {
    if (hikIpEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少海康地址", "请先填写海康设备 IP 地址。");
        return;
    }
    if (streamProbeProcess_ != nullptr && streamProbeProcess_->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "正在测试", "视频流连接测试正在进行。");
        return;
    }

    applyHikvisionStream();
    auto* process = new QProcess(this);
    streamProbeProcess_ = process;
    process->setProcessChannelMode(QProcess::MergedChannels);
    connect(process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, [this, process](
        int exitCode,
        QProcess::ExitStatus
    ) {
        const QByteArray output = process->readAllStandardOutput().trimmed();
        streamProbeProcess_ = nullptr;
        process->deleteLater();
        if (exitCode == 0) {
            appendLog("视频流连接测试通过。");
            QMessageBox::information(this, "连接成功", "海康视频流可以正常读取。");
        } else {
            QString message = "海康视频流连接失败。";
            const QList<QByteArray> lines = output.split('\n');
            if (!lines.isEmpty()) {
                const QJsonDocument document = QJsonDocument::fromJson(lines.last().trimmed());
                if (document.isObject()) {
                    message = document.object().value("message").toString(message);
                }
            }
            appendLog(message);
            QMessageBox::warning(this, "连接失败", message);
        }
    });
    process->start(
        RuntimePaths::workerExePath(),
        {
            "probe-source",
            "--source", buildHikvisionRtsp(),
            "--rtsp-transport", hikTransportCombo_->currentData().toString()
        }
    );
    if (!process->waitForStarted(3000)) {
        streamProbeProcess_ = nullptr;
        process->deleteLater();
        QMessageBox::critical(this, "连接测试失败", "无法启动视频流测试进程。");
        return;
    }
    appendLog("正在测试海康视频流连接。");
}

void MainWindow::browseOutput() {
    const QString path = QFileDialog::getExistingDirectory(this, "选择输出目录", privatePath(outputEdit_));
    if (!path.isEmpty()) {
        setPrivatePath(outputEdit_, path, true);
        saveSettings();
    }
}

void MainWindow::addRegion() {
    RegionConfig region;
    region.id = nextRegionId();
    region.name = QString("区域 %1").arg(regions_.size() + 1);
    region.priority = regions_.size() + 1;
    regions_.push_back(region);
    currentRegionId_ = region.id;
    refreshRegionSelectors();
    applyRegionSelection();
    appendLog("已新增区域：" + region.name);
}

void MainWindow::renameCurrentRegion() {
    const int index = findRegionIndexById(currentRegionId_);
    if (index < 0) {
        return;
    }
    const QString name = regionNameEdit_->text().trimmed();
    if (name.isEmpty()) {
        QMessageBox::warning(this, "区域配置错误", "区域名称不能为空。");
        regionNameEdit_->setText(regions_[index].name);
        return;
    }
    regions_[index].name = name;
    refreshRegionSelectors();
    applyRegionSelection();
}

void MainWindow::deleteCurrentRegion() {
    if (regions_.size() <= 1) {
        QMessageBox::warning(this, "无法删除", "至少保留一个区域。");
        return;
    }
    const int index = findRegionIndexById(currentRegionId_);
    if (index < 0) {
        return;
    }
    QString nextTotalCountRegionId = totalCountRegionId_;
    if (totalCountRegionId_ == currentRegionId_) {
        nextTotalCountRegionId.clear();
        for (int i = 0; i < regions_.size(); ++i) {
            if (i != index && regions_[i].countEnabled) {
                nextTotalCountRegionId = regions_[i].id;
                break;
            }
        }
        if (nextTotalCountRegionId.isEmpty()) {
            QMessageBox::warning(this, "无法删除", "没有可作为主统计区域的计数区域，请先启用其他区域的累计。");
            return;
        }
    }
    const QString removedName = regions_[index].name;
    regions_.removeAt(index);
    if (totalCountRegionId_ == currentRegionId_) {
        totalCountRegionId_ = nextTotalCountRegionId;
    }
    currentRegionId_ = regions_.first().id;
    refreshRegionSelectors();
    applyRegionSelection();
    appendLog("已删除区域：" + removedName);
}

void MainWindow::saveRegionConfig() {
    try {
        updateDetectRoiFromEditor();
        const RegionConfigDocument document = buildRegionConfigDocument();
        saveRegionConfigDocument(RuntimePaths::defaultRegionsConfigPath(), document);
        appendLog("已保存区域配置：regions.json");
    } catch (const std::exception& ex) {
        QMessageBox::critical(this, "保存失败", QString::fromUtf8(ex.what()));
    }
}

void MainWindow::loadRegionConfig() {
    const QString initialPath = QFileInfo::exists(RuntimePaths::defaultRegionsConfigPath())
        ? RuntimePaths::defaultRegionsConfigPath()
        : RuntimePaths::regionsExamplePath();
    const QString path = QFileDialog::getOpenFileName(
        this,
        "加载区域配置",
        initialPath,
        "区域配置 (*.json)"
    );
    if (path.isEmpty()) {
        return;
    }
    try {
        restoreRegionConfigDocument(loadRegionConfigDocument(path));
        appendLog("已加载区域配置：" + QFileInfo(path).fileName());
    } catch (const std::exception& ex) {
        QMessageBox::critical(this, "加载失败", QString::fromUtf8(ex.what()));
    }
}

DetectJobConfig MainWindow::currentDetectConfig() const {
    const QString outputDir = privatePath(outputEdit_);
    return {
        privatePath(modelEdit_),
        privatePath(sourceEdit_),
        hikTransportCombo_->currentData().toString(),
        outputDir,
        RuntimePaths::workerExePath(),
        RuntimePaths::trackerConfigPath(),
        QDir(outputDir).filePath("regions.json"),
        detectRoiEdit_->text().trimmed(),
        QDir(outputDir).filePath("jam_signals.jsonl"),
        loadedLabels_,
        classCombo_->currentData().toInt(),
        inputSizeSpin_->value(),
        confidenceSpin_->value(),
        iouSpin_->value(),
        deviceCombo_->currentData().toString(),
        videoFpsSpin_->value(),
        jamSecondsSpin_->value()
    };
}

void MainWindow::startDetection() {
    if (workerThread_ != nullptr) {
        QMessageBox::information(this, "任务运行中", "检测正在运行。");
        return;
    }
    if (!QFileInfo::exists(RuntimePaths::workerExePath())) {
        QMessageBox::critical(this, "缺少 worker exe", "未找到安装目录 runtime 下的 worker exe。");
        return;
    }
    if (!QFileInfo::exists(privatePath(modelEdit_))) {
        QMessageBox::warning(this, "缺少模型", "请先在推理参数中选择 PT、ONNX 或 OpenVINO 模型。");
        return;
    }
    if (privatePath(sourceEdit_).isEmpty()) {
        QMessageBox::warning(this, "缺少视频源", "请先选择或填写视频源。");
        return;
    }
    if (!canBeRuntimeSource(privatePath(sourceEdit_)) && !QFileInfo::exists(privatePath(sourceEdit_))) {
        QMessageBox::warning(this, "视频源不存在", "当前视频源不是本地文件、摄像头编号或网络流。");
        return;
    }
    if (!QFileInfo::exists(RuntimePaths::trackerConfigPath())) {
        QMessageBox::critical(this, "缺少 tracker yaml", "未找到随程序发布的 ByteTrack tracker yaml。");
        return;
    }
    QString outputError;
    if (!isOutputDirWritable(privatePath(outputEdit_), &outputError)) {
        QMessageBox::warning(this, "输出目录不可写", outputError);
        return;
    }
    const QString modelPath = privatePath(modelEdit_);
    if (loadedModelPath_ != modelPath || loadedLabels_.isEmpty()) {
        beginModelMetadataRefresh(true);
        return;
    }

    try {
        updateDetectRoiFromEditor();
        const RegionConfigDocument document = buildRegionConfigDocument();
        saveRegionConfigDocument(RuntimePaths::defaultRegionsConfigPath(), document);
        const QString runRegionPath = QDir(privatePath(outputEdit_)).filePath("regions.json");
        saveRegionConfigDocument(runRegionPath, document);
    } catch (const std::exception& ex) {
        QMessageBox::critical(this, "区域配置错误", QString::fromUtf8(ex.what()));
        return;
    }

    saveSettings();
    regionRuntimeStates_.clear();
    dashboardTotalCount_ = 0;
    dashboardInsideCount_ = 0;
    dashboardJamCount_ = 0;
    dashboardJamActive_ = false;
    dashboardFlashVisible_ = false;
    dashboardStatusText_ = "启动中";
    refreshRegionTable();

    workerThread_ = new QThread(this);
    refreshRegionTable();
    worker_ = new DetectionWorker(currentDetectConfig());
    worker_->moveToThread(workerThread_);
    connect(workerThread_, &QThread::started, worker_, &DetectionWorker::run);
    connect(worker_, &DetectionWorker::frameReady, this, &MainWindow::showFrame);
    connect(worker_, &DetectionWorker::dashboardPayloadReady, this, &MainWindow::updateDashboard);
    connect(worker_, &DetectionWorker::log, this, &MainWindow::appendLog);
    connect(worker_, &DetectionWorker::done, this, &MainWindow::detectionFinished);
    connect(worker_, &DetectionWorker::failed, this, &MainWindow::detectionFailed);
    connect(worker_, &DetectionWorker::done, workerThread_, &QThread::quit);
    connect(worker_, &DetectionWorker::failed, workerThread_, &QThread::quit);
    connect(workerThread_, &QThread::finished, worker_, &QObject::deleteLater);
    connect(workerThread_, &QThread::finished, this, &MainWindow::cleanupWorker);
    startButton_->setEnabled(false);
    stopButton_->setEnabled(true);
    setConfigurationEditingEnabled(false);
    workerThread_->start();
}

void MainWindow::stopDetection() {
    if (worker_ != nullptr) {
        QMetaObject::invokeMethod(worker_, "stop", Qt::DirectConnection);
    }
}

void MainWindow::showFrame(const QImage& image) {
    previewLabel_->setImage(image);
}

void MainWindow::updateDashboard(const QByteArray& payload) {
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(payload, &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        appendLog("看板更新失败：JSON 解析错误。");
        return;
    }
    const QJsonObject object = document.object();
    const QString type = object.value("type").toString();
    const QString eventType = object.value("event_type").toString();

    if (type == "frame" || type == "done") {
        QVector<RegionRuntimeState> states;
        const QJsonArray regionsArray = object.value("regions").toArray();
        if (!regionsArray.isEmpty()) {
            states.reserve(regionsArray.size());
            for (const QJsonValue& value : regionsArray) {
                if (value.isObject()) {
                    states.push_back(regionRuntimeStateFromJson(value.toObject()));
                }
            }
        } else if (!regions_.isEmpty()) {
            RegionRuntimeState state = buildFallbackState(regions_.first());
            state.flowCount = object.value("flow_count").toInt();
            state.insideCount = object.value("inside_count").toInt();
            state.jamCount = object.value("jam_count").toInt();
            state.maxInsideCount = object.value("max_inside_count").toInt();
            state.jamActive = object.value("jam_active").toBool();
            state.status = state.jamActive ? "堵包" : "运行中";
            states.push_back(state);
        }
        regionRuntimeStates_ = states;
        dashboardTotalCount_ = object.contains("total_count")
            ? object.value("total_count").toInt()
            : object.value("flow_count").toInt();
        if (!regionsArray.isEmpty()) {
            dashboardInsideCount_ = 0;
            for (const RegionRuntimeState& state : regionRuntimeStates_) {
                dashboardInsideCount_ += state.insideCount;
            }
        } else {
            dashboardInsideCount_ = object.value("inside_count").toInt();
        }
        if (!regionsArray.isEmpty()) {
            dashboardJamCount_ = 0;
            for (const RegionRuntimeState& state : regionRuntimeStates_) {
                dashboardJamCount_ += state.jamCount;
            }
        } else {
            dashboardJamCount_ = object.value("jam_count").toInt();
        }
        dashboardJamActive_ = object.value("jam_active").toBool();
        if (!dashboardJamActive_) {
            for (const RegionRuntimeState& state : regionRuntimeStates_) {
                if (state.jamActive) {
                    dashboardJamActive_ = true;
                    break;
                }
            }
        }
        const QString fallbackStatus = type == "done"
            ? QStringLiteral("已完成")
            : object.value("global_status").toString();
        dashboardStatusText_ = dashboardStatusForStates(regionRuntimeStates_, dashboardJamActive_, fallbackStatus);
        if (type == "done" && !dashboardJamActive_) {
            dashboardStatusText_ = "已完成";
        }
        setDashboardAlarmActive(dashboardJamActive_);
        refreshRegionTable();
    }

    if (type == "jam") {
        const bool isClear = eventType == "jam_cleared";
        if (object.contains("region_id")) {
            const QString regionId = object.value("region_id").toString();
            int stateIndex = -1;
            for (int i = 0; i < regionRuntimeStates_.size(); ++i) {
                if (regionRuntimeStates_[i].id == regionId) {
                    stateIndex = i;
                    break;
                }
            }
            if (stateIndex < 0) {
                RegionRuntimeState state;
                state.id = regionId;
                state.name = object.value("region_name").toString();
                regionRuntimeStates_.push_back(state);
                stateIndex = regionRuntimeStates_.size() - 1;
            }
            RegionRuntimeState& state = regionRuntimeStates_[stateIndex];
            state.id = regionId;
            state.name = object.value("region_name").toString(state.name);
            state.signal = object.value("signal").toString();
            state.eventType = eventType;
            state.insideCount = object.value("inside_count").toInt(state.insideCount);
            state.flowCount = object.value("flow_count").toInt(state.flowCount);
            state.jamCount = object.value("jam_count").toInt(state.jamCount);
            state.staleSeconds = object.value("stale_seconds").toDouble(state.staleSeconds);
            state.jamActive = !isClear;
            state.status = isClear
                ? (state.insideCount <= 0 ? "空闲" : "运行中")
                : "堵包";
        } else if (isClear) {
            for (RegionRuntimeState& state : regionRuntimeStates_) {
                state.jamActive = false;
                state.status = state.insideCount <= 0 ? "空闲" : "运行中";
            }
        }

        dashboardJamActive_ = false;
        dashboardInsideCount_ = 0;
        dashboardJamCount_ = 0;
        for (const RegionRuntimeState& state : regionRuntimeStates_) {
            dashboardInsideCount_ += state.insideCount;
            dashboardJamCount_ += state.jamCount;
            if (state.id == totalCountRegionId_) {
                dashboardTotalCount_ = state.flowCount;
            }
            if (state.jamActive) {
                dashboardJamActive_ = true;
            }
        }
        dashboardStatusText_ = dashboardStatusForStates(regionRuntimeStates_, dashboardJamActive_, "运行中");
        setDashboardAlarmActive(dashboardJamActive_);
        refreshRegionTable();

        const QString regionName = object.value("region_name").toString();
        if (isClear) {
            appendLog(QString("堵包解除：%1，信号 %2").arg(regionName, object.value("signal").toString()));
        } else {
            appendLog(
                QString("堵包报警：%1，区域内 %2 个，停滞 %3 秒，信号 %4")
                    .arg(regionName)
                    .arg(object.value("inside_count").toInt())
                    .arg(object.value("stale_seconds").toDouble(), 0, 'f', 1)
                    .arg(object.value("signal").toString())
            );
        }
    } else if (type == "jam_clear") {
        const int legacyInsideCount = object.value("inside_count").toInt();
        for (RegionRuntimeState& state : regionRuntimeStates_) {
            state.jamActive = false;
            state.insideCount = legacyInsideCount;
            state.status = state.insideCount <= 0 ? "空闲" : "运行中";
        }
        dashboardJamActive_ = false;
        dashboardInsideCount_ = legacyInsideCount;
        dashboardStatusText_ = dashboardStatusForStates(regionRuntimeStates_, false, "运行中");
        setDashboardAlarmActive(false);
        refreshRegionTable();
        appendLog("堵包解除，信号 " + object.value("signal").toString());
    }
}

void MainWindow::appendLog(const QString& message) {
    const QString text = message.trimmed();
    if (!text.isEmpty()) {
        logEdit_->appendPlainText(QDateTime::currentDateTime().toString("HH:mm:ss ") + text);
    }
}

void MainWindow::refreshModelMetadata() {
    beginModelMetadataRefresh(false);
}

void MainWindow::beginModelMetadataRefresh(bool startDetectionAfterSuccess) {
    const QString modelPath = privatePath(modelEdit_);
    if (!QFileInfo::exists(RuntimePaths::workerExePath()) || !QFileInfo::exists(modelPath)) {
        if (modelInspectProcess_ != nullptr) {
            modelInspectProcess_->disconnect(this);
            if (modelInspectProcess_->state() != QProcess::NotRunning) {
                modelInspectProcess_->kill();
            }
            modelInspectProcess_->deleteLater();
            modelInspectProcess_ = nullptr;
            modelInspectPath_.clear();
            startDetectionAfterModelInspect_ = false;
            modelInspectTimedOut_ = false;
            startButton_->setEnabled(workerThread_ == nullptr);
        }
        loadedLabels_.clear();
        loadedModelPath_.clear();
        populateClassCombo({});
        if (startDetectionAfterSuccess) {
            QMessageBox::warning(this, "模型读取失败", "未找到模型文件或 worker exe，检测未启动。");
        }
        return;
    }
    if (loadedModelPath_ == modelPath && !loadedLabels_.isEmpty()) {
        if (startDetectionAfterSuccess) {
            QTimer::singleShot(0, this, &MainWindow::startDetection);
        }
        return;
    }

    if (modelInspectProcess_ != nullptr) {
        if (modelInspectProcess_->state() != QProcess::NotRunning && modelInspectPath_ == modelPath) {
            startDetectionAfterModelInspect_ =
                startDetectionAfterModelInspect_ || startDetectionAfterSuccess;
            if (startDetectionAfterModelInspect_) {
                startButton_->setEnabled(false);
            }
            return;
        }
        modelInspectProcess_->disconnect(this);
        if (modelInspectProcess_->state() != QProcess::NotRunning) {
            modelInspectProcess_->kill();
        }
        modelInspectProcess_->deleteLater();
        modelInspectProcess_ = nullptr;
        startButton_->setEnabled(workerThread_ == nullptr);
    }

    modelInspectPath_ = modelPath;
    startDetectionAfterModelInspect_ = startDetectionAfterSuccess;
    modelInspectTimedOut_ = false;
    if (startDetectionAfterModelInspect_) {
        startButton_->setEnabled(false);
    }
    appendLog("正在读取模型类别：" + QFileInfo(modelPath).fileName());

    auto* process = new QProcess(this);
    modelInspectProcess_ = process;
    process->setProcessChannelMode(QProcess::MergedChannels);
    connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            finishModelMetadataRefresh(process, "worker 进程启动失败。");
        }
    });
    connect(
        process,
        qOverload<int, QProcess::ExitStatus>(&QProcess::finished),
        this,
        [this, process](int exitCode, QProcess::ExitStatus exitStatus) {
            QString failure;
            if (modelInspectTimedOut_) {
                failure = "worker 进程 30 秒内未完成。";
            } else if (exitStatus != QProcess::NormalExit || exitCode != 0) {
                failure = QString::fromUtf8(process->readAllStandardOutput()).trimmed();
                if (failure.isEmpty()) {
                    failure = QString("worker 异常退出，代码 %1。").arg(exitCode);
                }
            }
            finishModelMetadataRefresh(process, failure);
        }
    );
    process->start(RuntimePaths::workerExePath(), inspectModelArgs(modelPath));
    QTimer::singleShot(30000, this, [this, process]() {
        if (modelInspectProcess_ == process && process->state() != QProcess::NotRunning) {
            modelInspectTimedOut_ = true;
            process->kill();
        }
    });
}

void MainWindow::finishModelMetadataRefresh(QProcess* process, const QString& failure) {
    if (process == nullptr || process != modelInspectProcess_) {
        return;
    }

    const bool startAfterSuccess = startDetectionAfterModelInspect_;
    const QString modelPath = modelInspectPath_;
    const QByteArray output = process->readAllStandardOutput();
    modelInspectProcess_ = nullptr;
    modelInspectPath_.clear();
    startDetectionAfterModelInspect_ = false;
    modelInspectTimedOut_ = false;
    process->deleteLater();

    QString error = failure.trimmed();
    const QStringList labels = error.isEmpty() ? parseClassLabelsFromJson(output) : QStringList{};
    if (error.isEmpty() && labels.isEmpty()) {
        error = "worker 未返回有效的模型类别。";
    }
    if (!error.isEmpty()) {
        appendLog("模型类别读取失败：" + error);
        loadedLabels_.clear();
        loadedModelPath_.clear();
        populateClassCombo({});
        startButton_->setEnabled(workerThread_ == nullptr);
        if (startAfterSuccess) {
            QMessageBox::warning(this, "模型读取失败", error + "\n检测未启动。");
        }
        return;
    }

    loadedLabels_ = labels;
    loadedModelPath_ = modelPath;
    populateClassCombo(loadedLabels_);
    appendLog("已读取模型类别：" + loadedLabels_.join(", "));
    startButton_->setEnabled(workerThread_ == nullptr);
    if (startAfterSuccess) {
        QTimer::singleShot(0, this, &MainWindow::startDetection);
    }
}

void MainWindow::runEnvironmentDiagnose() {
    if (!QFileInfo::exists(RuntimePaths::workerExePath())) {
        appendLog("环境自检失败：缺少 cvds_detector_worker.exe。");
        QMessageBox::critical(this, "环境自检失败", "未找到安装目录 runtime 下的 worker exe。");
        return;
    }

    QProcess process;
    process.setProcessChannelMode(QProcess::MergedChannels);
    process.start(RuntimePaths::workerExePath(), {"diagnose"});
    if (!process.waitForStarted(5000)) {
        appendLog("环境自检失败：worker 进程启动失败。");
        return;
    }
    if (!process.waitForFinished(30000)) {
        process.kill();
        process.waitForFinished(3000);
        appendLog("环境自检失败：worker 进程 30 秒内未完成。");
        return;
    }
    const QByteArray output = process.readAllStandardOutput();
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(output.trimmed(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        appendLog("环境自检失败：" + QString::fromUtf8(output).trimmed());
        return;
    }

    const QJsonObject object = document.object();
    appendLog("环境自检：Python 运行时 " + QString(object.value("python_runtime").toBool() ? "正常" : "异常"));
    appendLog("环境自检：Torch " + QString(object.value("torch_available").toBool() ? "可用" : "不可用"));
    if (!object.value("torch_version").toString().isEmpty()) {
        appendLog("环境自检：Torch 版本 " + object.value("torch_version").toString());
    }
    appendLog("环境自检：Torch CUDA 版本 " + QString(object.value("torch_cuda_version").toString().isEmpty() ? "未启用" : object.value("torch_cuda_version").toString()));
    appendLog("环境自检：Ultralytics " + QString(object.value("ultralytics_available").toBool() ? "可用" : "不可用"));
    appendLog("环境自检：OpenCV " + QString(object.value("opencv_available").toBool() ? "可用" : "不可用"));
    appendLog("环境自检：ONNX Runtime " + QString(object.value("onnxruntime_available").toBool() ? "可用" : "不可用"));
    appendLog("环境自检：OpenVINO " + QString(object.value("openvino_available").toBool() ? "可用" : "不可用"));
    const bool nvidiaAvailable = object.value("nvidia_driver_available").toBool();
    const QString nvidiaName = object.value("nvidia_gpu_name").toString();
    const QString nvidiaDriver = object.value("nvidia_driver_version").toString();
    appendLog("环境自检：NVIDIA 驱动/GPU " + QString(nvidiaAvailable ? "可见" : "不可见"));
    if (nvidiaAvailable) {
        appendLog("环境自检：NVIDIA 设备 " + nvidiaName + "，驱动 " + nvidiaDriver);
    }
    appendLog("环境自检：CUDA " + QString(object.value("cuda_available").toBool() ? "可用" : "不可用"));
    appendLog("环境自检：推荐设备 " + object.value("recommend_device").toString());
    const QString cudaIssue = object.value("cuda_issue").toString();
    if (!cudaIssue.isEmpty()) {
        appendLog("环境自检：" + cudaIssue);
    }
    const QJsonArray errors = object.value("errors").toArray();
    for (const QJsonValue& value : errors) {
        appendLog("环境自检错误：" + value.toString());
    }
}

void MainWindow::detectionFinished(const QString& summary) {
    dashboardStatusText_ = dashboardJamActive_ ? "堵包" : "已完成";
    refreshRegionTable();
    appendLog(summary);
}

void MainWindow::detectionFailed(const QString& error) {
    dashboardStatusText_ = "失败";
    setDashboardAlarmActive(false);
    refreshRegionTable();
    appendLog(error);
    QMessageBox::critical(this, "检测失败", error);
}

void MainWindow::cleanupWorker() {
    worker_ = nullptr;
    if (workerThread_ != nullptr) {
        workerThread_->deleteLater();
        workerThread_ = nullptr;
    }
    startButton_->setEnabled(true);
    stopButton_->setEnabled(false);
    setConfigurationEditingEnabled(true);
    refreshRuntimeOverview();
    refreshRegionTable();
}

void MainWindow::setConfigurationEditingEnabled(bool enabled) {
    if (pathPanel_ != nullptr) {
        pathPanel_->setEnabled(enabled);
    }
    if (paramPanel_ != nullptr) {
        paramPanel_->setEnabled(enabled);
    }
    if (roiPanel_ != nullptr) {
        roiPanel_->setEnabled(enabled);
    }
    if (controlPanel_ != nullptr) {
        controlPanel_->setEnabled(enabled);
    }
    if (previewLabel_ != nullptr) {
        previewLabel_->setRoiEditingEnabled(enabled);
    }
}

void MainWindow::setDashboardAlarmActive(bool active) {
    dashboardJamActive_ = active;
    if (active) {
        dashboardFlashVisible_ = true;
        if (!flashTimer_->isActive()) {
            flashTimer_->start();
        }
    } else {
        flashTimer_->stop();
        dashboardFlashVisible_ = false;
    }
    previewLabel_->setAlertFlashVisible(dashboardFlashVisible_);
    updateAlertStyle();
}

void MainWindow::toggleAlarmFlash() {
    dashboardFlashVisible_ = !dashboardFlashVisible_;
    previewLabel_->setAlertFlashVisible(dashboardFlashVisible_);
    updateAlertStyle();
    refreshRegionTable();
}

void MainWindow::updateAlertStyle() {
    if (dashboardRoot_ == nullptr) {
        return;
    }
    if (!dashboardFlashVisible_) {
        dashboardRoot_->setStyleSheet({});
        return;
    }
    dashboardRoot_->setStyleSheet(
        "QWidget#dashboardRoot QFrame#monitorPanel{border:2px solid #F25555;}"
        "QWidget#dashboardRoot QFrame#dashboardCard{border:1px solid #8D343C;border-left:3px solid #F25555;}"
        "QWidget#dashboardRoot QTableWidget{border:1px solid #8D343C;}"
    );
}

void MainWindow::loadVideoPreviewFrame() {
    const QString source = privatePath(sourceEdit_);
    if (source.isEmpty() || (!canBeRuntimeSource(source) && !QFileInfo::exists(source))) {
        return;
    }
    if (canBeRuntimeSource(source)) {
        appendLog("实时视频流将在开始检测后显示，避免连接异常阻塞界面。");
        return;
    }
    cv::VideoCapture cap = openCapture(source);
    if (!cap.isOpened()) {
        appendLog("视频首帧读取失败。");
        return;
    }
    cv::Mat frame;
    if (!cap.read(frame) || frame.empty()) {
        appendLog("视频首帧为空。");
        return;
    }
    previewLabel_->setImage(matToImage(frame));
    appendLog(QString("已载入视频首帧：%1 x %2").arg(frame.cols).arg(frame.rows));
}
