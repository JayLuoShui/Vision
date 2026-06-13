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
#include <QScrollArea>
#include <QScrollBar>
#include <QSettings>
#include <QSignalBlocker>
#include <QSizePolicy>
#include <QSpinBox>
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
    const QStringList names = weightsDir.entryList({"*.pt"}, QDir::Files, QDir::Name);
    if (names.isEmpty()) {
        return {};
    }
    return weightsDir.filePath(names.first());
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
    setMinimumSize(720, 520);
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
    painter.fillRect(rect(), QColor("#101820"));

    const QRect imageRect = imageRectInLabel();
    if (image_.isNull() || imageRect.isEmpty()) {
        painter.setPen(QColor("#b8c4c2"));
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
            ? QColor("#ff4d4f")
            : (isCurrent ? QColor("#55b982") : QColor("#d49a20"));
        if (isCurrent) {
            drawPolygon(painter, flowRoi_, flowRoiClosed_, color, region.name + "（当前区域）");
        } else {
            drawPolygon(painter, region.polygon, region.polygonClosed, color, region.name);
        }
    }
    drawPolygon(painter, detectRoi_, detectRoiClosed_, QColor("#4aa3b5"), "检测ROI");

    const QVector<QPoint>& polygon = activePolygon();
    if (hasDraftCursor_ && !polygon.isEmpty() && !activeRoiClosed()) {
        painter.setPen(QPen(QColor("#1f6f50"), 2, Qt::DashLine));
        painter.drawLine(imageToLabelPoint(polygon.last()), imageToLabelPoint(draftCursor_));
        painter.setBrush(QColor("#1f6f50"));
        painter.drawEllipse(imageToLabelPoint(draftCursor_), 4, 4);
    }

    painter.setPen(QColor("#d8e0df"));
    painter.drawText(imageRect.adjusted(12, 18, -12, -18), Qt::AlignLeft | Qt::AlignTop, "当前区域: " + activeRegionId_);
    if (alertFlashVisible_ && !jamRegionIds_.isEmpty()) {
        painter.setPen(QPen(QColor("#ff4d4f"), 4));
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
        if (!QFileInfo::exists(config_.ptPath)) {
            throw std::runtime_error("PT 权重不存在");
        }
        if (!QFileInfo::exists(config_.trackerPath)) {
            throw std::runtime_error("缺少 tracker yaml");
        }
        if (!QFileInfo::exists(config_.regionsPath)) {
            throw std::runtime_error("缺少 regions.json");
        }
        QDir().mkpath(config_.outputDir);
        const QString previewPath = QDir(config_.outputDir).filePath("cvds_pt_preview.jpg");
        QStringList args = {
            "detect",
            "--weights", config_.ptPath,
            "--source", config_.sourcePath,
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
        emit log("worker 路径：" + config_.workerPath);
        emit log("模型路径：" + config_.ptPath);
        emit log("输出目录：" + config_.outputDir);
        emit log("区域配置：" + config_.regionsPath);
        emit log("检测模式：通过独立 worker 使用 PT 权重进行视频检测。");
        emit log("请求推理设备：" + config_.device);
        emit log("堵包信号文件：" + config_.jamSignalPath);
        QProcess process;
        process.setProcessChannelMode(QProcess::MergedChannels);
        process.start(config_.workerPath, args);
        if (!process.waitForStarted(5000)) {
            throw std::runtime_error("PT 检测进程启动失败");
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
            emit failed(errorMessage.isEmpty() ? "PT 检测进程异常退出，请查看日志。" : errorMessage);
            return;
        }
        emit done(doneSummary.isEmpty() ? "视频检测完成。" : doneSummary);
    } catch (const std::exception& ex) {
        emit failed(QString::fromUtf8(ex.what()));
    }
}

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent) {
    setWindowTitle("CVDS包裹流量检测工具 " + RuntimePaths::versionText());
    resize(1480, 940);
    setMinimumSize(1180, 760);

    auto* root = new QWidget(this);
    root->setObjectName("dashboardRoot");
    dashboardRoot_ = root;
    auto* layout = new QHBoxLayout(root);
    layout->setContentsMargins(12, 12, 12, 12);
    layout->setSpacing(12);

    auto* leftContent = new QWidget(root);
    leftContent->setMinimumWidth(500);
    auto* leftLayout = new QVBoxLayout(leftContent);
    leftLayout->setContentsMargins(0, 0, 8, 0);
    leftLayout->setSpacing(8);
    pathPanel_ = buildPathPanel();
    paramPanel_ = buildParamPanel();
    roiPanel_ = buildRoiPanel();
    leftLayout->addWidget(pathPanel_);
    leftLayout->addWidget(paramPanel_);
    leftLayout->addWidget(roiPanel_);
    leftLayout->addWidget(buildActionPanel());
    leftLayout->addStretch(1);

    auto* leftScroll = new QScrollArea(root);
    leftScroll->setWidgetResizable(true);
    leftScroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    leftScroll->setFrameShape(QFrame::NoFrame);
    leftScroll->setMinimumWidth(520);
    leftScroll->setMaximumWidth(680);
    leftScroll->verticalScrollBar()->setSingleStep(28);
    leftScroll->verticalScrollBar()->setPageStep(160);
    leftScroll->setWidget(leftContent);

    auto* right = new QWidget(root);
    auto* rightLayout = new QVBoxLayout(right);
    rightLayout->setContentsMargins(0, 0, 0, 0);
    rightLayout->setSpacing(10);
    rightLayout->addWidget(buildDashboardPanel());

    previewLabel_ = new RoiPreviewLabel(right);
    previewLabel_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    regionTable_ = new QTableWidget(0, 6, right);
    regionTable_->setHorizontalHeaderLabels({"区域状态", "累计包裹", "区域内", "当前状态", "堵包秒数", "堵包次数"});
    regionTable_->verticalHeader()->setVisible(false);
    regionTable_->horizontalHeader()->setStretchLastSection(true);
    regionTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    regionTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
    regionTable_->setSelectionMode(QAbstractItemView::NoSelection);
    regionTable_->setFocusPolicy(Qt::NoFocus);
    regionTable_->setMinimumHeight(210);

    logEdit_ = new QPlainTextEdit(right);
    logEdit_->setReadOnly(true);
    logEdit_->setMaximumHeight(180);

    rightLayout->addWidget(previewLabel_, 1);
    rightLayout->addWidget(regionTable_);
    rightLayout->addWidget(logEdit_);

    layout->addWidget(leftScroll);
    layout->addWidget(right, 1);
    setCentralWidget(root);

    setStyleSheet(
        "QWidget{background:#101820;color:#d8e0df;font-family:'Microsoft YaHei UI';font-size:12px;}"
        "QScrollArea{background:#101820;border:none;}"
        "QScrollBar:vertical{background:#0b1114;width:10px;margin:0;border:none;}"
        "QScrollBar::handle:vertical{background:#52676c;min-height:42px;border-radius:4px;}"
        "QScrollBar::handle:vertical:hover{background:#d49a20;}"
        "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:none;border:none;}"
        "QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}"
        "QGroupBox{border:1px solid #415357;border-radius:4px;margin-top:12px;padding:10px;color:#d49a20;background:#1f2a2e;}"
        "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;background:#1f2a2e;color:#d49a20;}"
        "QLabel{color:#c8d2d0;}"
        "QLabel#dashboardValue{font-size:24px;font-weight:700;color:#edf2f1;}"
        "QLineEdit,QPlainTextEdit,QComboBox,QTableWidget{background:#0b1114;border:1px solid #485b60;border-radius:2px;padding:6px;color:#edf2f1;selection-background-color:#d49a20;gridline-color:#334347;}"
        "QLineEdit:focus,QPlainTextEdit:focus,QComboBox:focus{border:1px solid #d49a20;}"
        "QSpinBox,QDoubleSpinBox{background:#0b1114;border:1px solid #485b60;border-radius:2px;padding:5px 30px 5px 6px;color:#edf2f1;selection-background-color:#d49a20;}"
        "QSpinBox:focus,QDoubleSpinBox:focus{border:1px solid #d49a20;}"
        "QSpinBox::up-button,QDoubleSpinBox::up-button{subcontrol-origin:border;subcontrol-position:top right;width:24px;background:#26363a;border-left:1px solid #52676c;border-bottom:1px solid #52676c;}"
        "QSpinBox::down-button,QDoubleSpinBox::down-button{subcontrol-origin:border;subcontrol-position:bottom right;width:24px;background:#26363a;border-left:1px solid #52676c;border-top:1px solid #52676c;}"
        "QSpinBox::up-button:hover,QDoubleSpinBox::up-button:hover,QSpinBox::down-button:hover,QDoubleSpinBox::down-button:hover{background:#34484d;}"
        "QSpinBox::up-arrow,QDoubleSpinBox::up-arrow{width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:7px solid #d49a20;}"
        "QSpinBox::down-arrow,QDoubleSpinBox::down-arrow{width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:7px solid #d49a20;}"
        "QComboBox::drop-down{background:#26363a;border-left:1px solid #52676c;width:26px;}"
        "QComboBox::down-arrow{width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-top:7px solid #d49a20;}"
        "QPushButton{background:#26363a;border:1px solid #5c7075;border-radius:2px;padding:8px;color:#edf2f1;}"
        "QPushButton:hover{background:#34484d;border-color:#d49a20;}"
        "QPushButton:checked{background:#1f6f50;border-color:#55b982;color:white;}"
        "QPushButton#primaryButton{background:#1f6f50;border-color:#55b982;color:white;font-weight:600;}"
        "QPushButton#primaryButton:hover{background:#26845f;}"
        "QPushButton#dangerButton{background:#8f1d1d;border-color:#c54a4a;color:white;font-weight:600;}"
        "QPushButton#dangerButton:hover{background:#a62727;}"
        "QPushButton:disabled{background:#252d30;border-color:#3b474a;color:#7f8f8c;}"
        "QCheckBox{spacing:8px;}"
        "QCheckBox::indicator{width:16px;height:16px;border:1px solid #5c7075;background:#0b1114;}"
        "QCheckBox::indicator:checked{background:#1f6f50;border:1px solid #55b982;}"
    );

    flashTimer_ = new QTimer(this);
    flashTimer_->setInterval(500);
    connect(flashTimer_, &QTimer::timeout, this, &MainWindow::toggleAlarmFlash);

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

    appendLog("已启动 PT 视频流量监测工具，版本：" + RuntimePaths::versionText());
    appendLog("worker 路径：" + RuntimePaths::workerExePath() + "（cvds_detector_worker.exe）");
    populateClassCombo({});
    loadSettings();
    if (QFileInfo::exists(RuntimePaths::defaultRegionsConfigPath())) {
        try {
            restoreRegionConfigDocument(loadRegionConfigDocument(RuntimePaths::defaultRegionsConfigPath()));
            appendLog("已加载区域配置：" + RuntimePaths::defaultRegionsConfigPath());
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
    if (workerThread_ != nullptr) {
        workerThread_->quit();
        workerThread_->wait();
    }
}

QWidget* MainWindow::buildPathPanel() {
    auto* box = new QGroupBox("路径");
    auto* layout = new QGridLayout(box);
    ptEdit_ = new QLineEdit(findDefaultModelPath(), box);
    sourceEdit_ = new QLineEdit(box);
    outputEdit_ = new QLineEdit(RuntimePaths::defaultOutputDir(), box);
    hikIpEdit_ = new QLineEdit(box);
    hikUserEdit_ = new QLineEdit("admin", box);
    hikPasswordEdit_ = new QLineEdit(box);
    hikChannelSpin_ = new ScrollSafeSpinBox(box);
    hikPasswordEdit_->setEchoMode(QLineEdit::Password);
    hikIpEdit_->setPlaceholderText("192.168.1.64");
    hikPasswordEdit_->setPlaceholderText("海康相机密码");
    hikChannelSpin_->setRange(1, 999);
    hikChannelSpin_->setValue(101);

    auto addRow = [&](int row, const QString& label, QLineEdit* edit, auto slot) {
        auto* button = new QPushButton(row == 1 ? "本地" : "选择", box);
        connect(button, &QPushButton::clicked, this, slot);
        layout->addWidget(new QLabel(label, box), row, 0);
        layout->addWidget(edit, row, 1);
        layout->addWidget(button, row, 2);
    };

    addRow(0, "视觉模型", ptEdit_, &MainWindow::browsePt);
    addRow(1, "视频源", sourceEdit_, &MainWindow::browseSource);
    addRow(2, "输出目录", outputEdit_, &MainWindow::browseOutput);
    layout->addWidget(new QLabel("海康相机", box), 3, 0);
    layout->addWidget(hikIpEdit_, 3, 1);
    auto* hikButton = new QPushButton("接入", box);
    connect(hikButton, &QPushButton::clicked, this, &MainWindow::applyHikvisionStream);
    layout->addWidget(hikButton, 3, 2);
    layout->addWidget(new QLabel("海康账号", box), 4, 0);
    auto* hikAuthLayout = new QHBoxLayout();
    hikAuthLayout->addWidget(hikUserEdit_);
    hikAuthLayout->addWidget(hikPasswordEdit_);
    layout->addLayout(hikAuthLayout, 4, 1, 1, 2);
    layout->addWidget(new QLabel("海康通道", box), 5, 0);
    layout->addWidget(hikChannelSpin_, 5, 1, 1, 2);

    connect(ptEdit_, &QLineEdit::editingFinished, this, &MainWindow::refreshModelMetadata);
    connect(sourceEdit_, &QLineEdit::editingFinished, this, &MainWindow::loadVideoPreviewFrame);
    return box;
}

QWidget* MainWindow::buildParamPanel() {
    auto* box = new QGroupBox("推理参数");
    auto* form = new QFormLayout(box);
    classCombo_ = new ScrollSafeComboBox(box);
    classCombo_->addItem("全部类别", -1);
    deviceCombo_ = new ScrollSafeComboBox(box);
    deviceCombo_->addItem("自动", "auto");
    deviceCombo_->addItem("CPU", "cpu");
    deviceCombo_->addItem("GPU", "0");
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

    auto* drawButtons = new QHBoxLayout();
    drawFlowRoiButton_ = new QPushButton("绘制流量ROI", box);
    drawDetectRoiButton_ = new QPushButton("绘制检测区域", box);
    auto* undoButton = new QPushButton("撤回ROI点", box);
    auto* clearButton = new QPushButton("清空当前ROI", box);
    drawFlowRoiButton_->setCheckable(true);
    drawDetectRoiButton_->setCheckable(true);
    drawFlowRoiButton_->setChecked(true);
    drawButtons->addWidget(drawFlowRoiButton_);
    drawButtons->addWidget(drawDetectRoiButton_);
    drawButtons->addWidget(undoButton);
    drawButtons->addWidget(clearButton);

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
    auto* box = new QGroupBox("操作");
    auto* layout = new QVBoxLayout(box);
    startButton_ = new QPushButton("开始检测", box);
    stopButton_ = new QPushButton("停止检测", box);
    diagnoseButton_ = new QPushButton("环境自检", box);
    startButton_->setObjectName("primaryButton");
    stopButton_->setObjectName("dangerButton");
    stopButton_->setEnabled(false);
    connect(startButton_, &QPushButton::clicked, this, &MainWindow::startDetection);
    connect(stopButton_, &QPushButton::clicked, this, &MainWindow::stopDetection);
    connect(diagnoseButton_, &QPushButton::clicked, this, &MainWindow::runEnvironmentDiagnose);
    layout->addWidget(diagnoseButton_);
    layout->addWidget(startButton_);
    layout->addWidget(stopButton_);
    return box;
}

QWidget* MainWindow::buildDashboardPanel() {
    auto* box = new QGroupBox("看板");
    auto* layout = new QGridLayout(box);

    auto buildCard = [box](const QString& title, QLabel** valueLabel) {
        auto* card = new QFrame(box);
        auto* cardLayout = new QVBoxLayout(card);
        cardLayout->setContentsMargins(10, 10, 10, 10);
        auto* titleLabel = new QLabel(title, card);
        *valueLabel = new QLabel("0", card);
        (*valueLabel)->setObjectName("dashboardValue");
        cardLayout->addWidget(titleLabel);
        cardLayout->addWidget(*valueLabel);
        return card;
    };

    layout->addWidget(buildCard("累计包裹", &kpiTotalCountValueLabel_), 0, 0);
    layout->addWidget(buildCard("当前状态", &kpiStatusValueLabel_), 0, 1);
    layout->addWidget(buildCard("区域内包裹", &kpiInsideCountValueLabel_), 1, 0);
    layout->addWidget(buildCard("堵包次数", &kpiJamCountValueLabel_), 1, 1);
    return box;
}

QString MainWindow::buildHikvisionRtsp() const {
    QUrl url;
    url.setScheme("rtsp");
    url.setHost(hikIpEdit_->text().trimmed());
    url.setPort(554);
    url.setUserName(hikUserEdit_->text().trimmed());
    url.setPassword(hikPasswordEdit_->text());
    url.setPath("/Streaming/Channels/" + QString::number(hikChannelSpin_->value()));
    return url.toString(QUrl::FullyEncoded);
}

void MainWindow::loadSettings() {
    QSettings settings;
    const QString savedModel = settings.value("lastModelPath", ptEdit_->text()).toString();
    ptEdit_->setText(QFileInfo::exists(savedModel) ? savedModel : findDefaultModelPath());
    sourceEdit_->setText(sourcePathForSettings(settings.value("lastSourcePath", sourceEdit_->text()).toString()));
    const QString savedOutput = settings.value("lastOutputDir", outputEdit_->text()).toString().trimmed();
    outputEdit_->setText(savedOutput.isEmpty() ? RuntimePaths::defaultOutputDir() : savedOutput);
    detectRoiEdit_->setText(settings.value("lastDetectRoi", detectRoiEdit_->text()).toString());
    hikIpEdit_->setText(settings.value("hikvisionIp", hikIpEdit_->text()).toString());
    hikUserEdit_->setText(settings.value("hikvisionUser", hikUserEdit_->text()).toString());
    settings.remove("hikvisionPassword");
    hikPasswordEdit_->clear();
    hikChannelSpin_->setValue(settings.value("hikvisionChannel", hikChannelSpin_->value()).toInt());
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
    settings.setValue("lastModelPath", ptEdit_->text().trimmed());
    settings.setValue("lastSourcePath", sourcePathForSettings(sourceEdit_->text()));
    settings.setValue("lastOutputDir", outputEdit_->text().trimmed());
    settings.setValue("lastDetectRoi", detectRoiEdit_->text().trimmed());
    settings.setValue("hikvisionIp", hikIpEdit_->text().trimmed());
    settings.setValue("hikvisionUser", hikUserEdit_->text().trimmed());
    settings.remove("hikvisionPassword");
    settings.setValue("hikvisionChannel", hikChannelSpin_->value());
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
            QString::number(state.staleSeconds, 'f', 1),
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
                item->setBackground(QColor("#8f1d1d"));
            } else if (region.id == currentRegionId_) {
                item->setBackground(QColor("#1f2a2e"));
            } else {
                item->setBackground(QColor("#0b1114"));
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
        kpiStatusValueLabel_->setStyleSheet("color:#ff4d4f;font-size:24px;font-weight:700;");
    } else {
        kpiStatusValueLabel_->setStyleSheet("color:#55b982;font-size:24px;font-weight:700;");
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

void MainWindow::browsePt() {
    const QString path = QFileDialog::getOpenFileName(this, "选择视觉模型", ptEdit_->text(), "视觉模型 (*.pt)");
    if (!path.isEmpty()) {
        ptEdit_->setText(path);
        refreshModelMetadata();
        saveSettings();
    }
}

void MainWindow::browseSource() {
    const QString path = QFileDialog::getOpenFileName(
        this,
        "选择视频源",
        sourceEdit_->text(),
        "Video (*.mp4 *.avi *.mkv *.mov);;All files (*.*)"
    );
    if (!path.isEmpty()) {
        sourceEdit_->setText(path);
        loadVideoPreviewFrame();
        saveSettings();
    }
}

void MainWindow::applyHikvisionStream() {
    if (hikIpEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少海康地址", "请先填写海康相机 IP 地址。");
        return;
    }
    sourceEdit_->setText(buildHikvisionRtsp());
    saveSettings();
    loadVideoPreviewFrame();
}

void MainWindow::browseOutput() {
    const QString path = QFileDialog::getExistingDirectory(this, "选择输出目录", outputEdit_->text());
    if (!path.isEmpty()) {
        outputEdit_->setText(path);
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
        appendLog("已保存区域配置：" + RuntimePaths::defaultRegionsConfigPath());
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
        appendLog("已加载区域配置：" + path);
    } catch (const std::exception& ex) {
        QMessageBox::critical(this, "加载失败", QString::fromUtf8(ex.what()));
    }
}

DetectJobConfig MainWindow::currentDetectConfig() const {
    const QString outputDir = outputEdit_->text().trimmed();
    return {
        ptEdit_->text().trimmed(),
        sourceEdit_->text().trimmed(),
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
    if (!QFileInfo::exists(ptEdit_->text().trimmed())) {
        QMessageBox::warning(this, "缺少 PT", "请先选择 PT 权重。");
        return;
    }
    if (sourceEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少视频源", "请先选择或填写视频源。");
        return;
    }
    if (!canBeRuntimeSource(sourceEdit_->text()) && !QFileInfo::exists(sourceEdit_->text().trimmed())) {
        QMessageBox::warning(this, "视频源不存在", "当前视频源不是本地文件、摄像头编号或网络流。");
        return;
    }
    if (!QFileInfo::exists(RuntimePaths::trackerConfigPath())) {
        QMessageBox::critical(this, "缺少 tracker yaml", "未找到随程序发布的 ByteTrack tracker yaml。");
        return;
    }
    QString outputError;
    if (!isOutputDirWritable(outputEdit_->text().trimmed(), &outputError)) {
        QMessageBox::warning(this, "输出目录不可写", outputError);
        return;
    }
    const QString modelPath = ptEdit_->text().trimmed();
    if (loadedModelPath_ != modelPath || loadedLabels_.isEmpty()) {
        beginModelMetadataRefresh(true);
        return;
    }

    try {
        updateDetectRoiFromEditor();
        const RegionConfigDocument document = buildRegionConfigDocument();
        saveRegionConfigDocument(RuntimePaths::defaultRegionsConfigPath(), document);
        const QString runRegionPath = QDir(outputEdit_->text().trimmed()).filePath("regions.json");
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
    const QString modelPath = ptEdit_->text().trimmed();
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
        appendLog("环境自检失败：缺少 worker exe：" + RuntimePaths::workerExePath());
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
        "QWidget#dashboardRoot,QWidget#dashboardRoot QWidget{background:#4a0f12;}"
        "QWidget#dashboardRoot QGroupBox,QWidget#dashboardRoot QTableWidget,"
        "QWidget#dashboardRoot QPlainTextEdit{border:2px solid #ff4d4f;}"
    );
}

void MainWindow::loadVideoPreviewFrame() {
    const QString source = sourceEdit_->text().trimmed();
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
