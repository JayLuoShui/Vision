#include "MainWindow.h"
#include "RuntimePaths.h"

#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

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
#include <QSizePolicy>
#include <QSpinBox>
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

void RoiPreviewLabel::clearCurrentRoi() {
    activePolygon().clear();
    activeRoiClosed() = false;
    hasDraftCursor_ = false;
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
    emitCurrentRoi();
    update();
}

void RoiPreviewLabel::finishCurrentPolygon() {
    hasDraftCursor_ = false;
    activeRoiClosed() = activePolygon().size() >= 3;
    emitCurrentRoi();
    update();
}

void RoiPreviewLabel::setFlowRoiFromText(const QString& text) {
    flowRoi_ = textToPolygon(text);
    flowRoiClosed_ = flowRoi_.size() >= 3;
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
    QStringList parts;
    parts.reserve(polygon.size() * 2);
    for (const QPoint& point : polygon) {
        parts << QString::number(point.x()) << QString::number(point.y());
    }
    return parts.join(",");
}

QVector<QPoint> RoiPreviewLabel::textToPolygon(const QString& text) const {
    const QStringList parts = text.split(",", Qt::SkipEmptyParts);
    if (parts.size() < 6 || parts.size() % 2 != 0) {
        return {};
    }
    QVector<QPoint> polygon;
    polygon.reserve(parts.size() / 2);
    for (int i = 0; i + 1 < parts.size(); i += 2) {
        bool okX = false;
        bool okY = false;
        int x = parts[i].trimmed().toInt(&okX);
        int y = parts[i + 1].trimmed().toInt(&okY);
        if (!okX || !okY) {
            return {};
        }
        if (!image_.isNull()) {
            x = std::clamp(x, 0, image_.width() - 1);
            y = std::clamp(y, 0, image_.height() - 1);
        }
        polygon.push_back(QPoint(x, y));
    }
    return polygon;
}

void RoiPreviewLabel::emitCurrentRoi() {
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

    drawPolygon(painter, flowRoi_, flowRoiClosed_, QColor("#d49a20"), "流量ROI");
    drawPolygon(painter, detectRoi_, detectRoiClosed_, QColor("#4aa3b5"), "检测ROI");

    const QVector<QPoint>& polygon = activePolygon();
    if (hasDraftCursor_ && !polygon.isEmpty() && !activeRoiClosed()) {
        painter.setPen(QPen(QColor("#1f6f50"), 2, Qt::DashLine));
        painter.drawLine(imageToLabelPoint(polygon.last()), imageToLabelPoint(draftCursor_));
        painter.setBrush(QColor("#1f6f50"));
        painter.drawEllipse(imageToLabelPoint(draftCursor_), 4, 4);
    }
}

void RoiPreviewLabel::mousePressEvent(QMouseEvent* event) {
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
    if (activeRoiClosed()) {
        activePolygon().clear();
    }
    activeRoiClosed() = false;
    activePolygon().push_back(labelToImagePoint(event->pos()));
    hasDraftCursor_ = false;
    emitCurrentRoi();
    update();
    event->accept();
}

void RoiPreviewLabel::mouseMoveEvent(QMouseEvent* event) {
    if (image_.isNull() || activePolygon().isEmpty() || activeRoiClosed()) {
        return;
    }
    draftCursor_ = labelToImagePoint(event->pos());
    hasDraftCursor_ = true;
    update();
}

void RoiPreviewLabel::keyPressEvent(QKeyEvent* event) {
    if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter) {
        finishCurrentPolygon();
        event->accept();
        return;
    }
    if (event->key() == Qt::Key_Escape
        || event->key() == Qt::Key_Backspace
        || (event->matches(QKeySequence::Undo))) {
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
        QDir().mkpath(config_.outputDir);
        const QString previewPath = QDir(config_.outputDir).filePath("cvds_pt_preview.jpg");
        QStringList args = {
            "detect",
            "--weights", config_.ptPath,
            "--source", config_.sourcePath,
            "--output-dir", config_.outputDir,
            "--preview-path", previewPath,
            "--roi", config_.flowRoiText,
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
                    const int frame = object.value("frame").toInt();
                    if (frame % std::max(1, config_.previewFps) == 0) {
                        emit log(
                            QString("已处理 %1 帧，流量 %2，ROI内 %3")
                                .arg(frame)
                                .arg(object.value("flow_count").toInt())
                                .arg(object.value("inside_count").toInt())
                        );
                    }
                } else if (type == "jam") {
                    emit log(
                        QString("堵包报警：ROI内 %1 个目标，%2 秒无流量更新，信号 %3")
                            .arg(object.value("inside_count").toInt())
                            .arg(object.value("stale_seconds").toDouble(), 0, 'f', 1)
                            .arg(object.value("signal").toString())
                    );
                } else if (type == "jam_clear") {
                    emit log("堵包解除，信号 " + object.value("signal").toString());
                } else if (type == "done") {
                    doneSummary = QString("视频检测完成：总帧 %1，流量 %2，堵包 %3 次，最大同时在ROI内 %4。输出：%5")
                        .arg(object.value("frames").toInt())
                        .arg(object.value("flow_count").toInt())
                        .arg(object.value("jam_count").toInt())
                        .arg(object.value("max_inside_count").toInt())
                        .arg(object.value("output_video").toString());
                } else if (type == "error") {
                    errorMessage = object.value("message").toString();
                    emit log("检测错误：" + errorMessage);
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
    setWindowTitle("CVDS包裹流量检测工具");
    resize(1420, 900);
    setMinimumSize(1100, 720);

    auto* root = new QWidget(this);
    auto* layout = new QHBoxLayout(root);
    layout->setContentsMargins(12, 12, 12, 12);
    layout->setSpacing(12);

    auto* leftContent = new QWidget(root);
    leftContent->setMinimumWidth(500);
    auto* leftLayout = new QVBoxLayout(leftContent);
    leftLayout->setContentsMargins(0, 0, 8, 0);
    leftLayout->setSpacing(8);
    leftLayout->addWidget(buildPathPanel());
    leftLayout->addWidget(buildParamPanel());
    leftLayout->addWidget(buildRoiPanel());
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
    previewLabel_ = new RoiPreviewLabel(right);
    previewLabel_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    logEdit_ = new QPlainTextEdit(right);
    logEdit_->setReadOnly(true);
    logEdit_->setMaximumHeight(170);
    rightLayout->addWidget(previewLabel_, 1);
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
        "QLineEdit,QPlainTextEdit,QComboBox{background:#0b1114;border:1px solid #485b60;border-radius:2px;padding:6px;color:#edf2f1;selection-background-color:#d49a20;}"
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
    );

    connect(previewLabel_, &RoiPreviewLabel::roiChanged, this, [this](RoiPreviewLabel::DrawMode mode, const QString& text) {
        if (mode == RoiPreviewLabel::DrawMode::FlowRoi) {
            flowRoiEdit_->setText(text);
        } else {
            detectRoiEdit_->setText(text);
        }
    });

    appendLog("已启动 PT 视频流量监测工具，版本：" + RuntimePaths::versionText());
    appendLog("worker 路径：" + RuntimePaths::workerExePath() + "（cvds_detector_worker.exe）");
    populateClassCombo({});
    loadSettings();
    appendLog("启动完成：已延迟加载模型类别和视频预览，选择模型或开始检测时再读取。");
}

MainWindow::~MainWindow() {
    saveSettings();
    stopDetection();
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
    flowRoiEdit_ = new QLineEdit(box);
    detectRoiEdit_ = new QLineEdit(box);
    jamSecondsSpin_ = new ScrollSafeSpinBox(box);
    jamSecondsSpin_->setRange(1, 600);
    jamSecondsSpin_->setValue(5);
    flowRoiEdit_->setPlaceholderText("左键加点，右键完成，Esc/Ctrl+Z撤回");
    detectRoiEdit_->setPlaceholderText("可选，只在该多边形区域检测");
    form->addRow("流量ROI", flowRoiEdit_);
    form->addRow("检测区域", detectRoiEdit_);
    form->addRow("堵包判定秒", jamSecondsSpin_);

    auto* help = new QLabel("ROI绘制：左键逐点绘制，多边形至少3点，右键完成，Esc或Ctrl+Z撤回上一个点。", box);
    help->setWordWrap(true);

    auto* buttons = new QHBoxLayout();
    drawFlowRoiButton_ = new QPushButton("绘制流量ROI", box);
    drawDetectRoiButton_ = new QPushButton("绘制检测区域", box);
    auto* undoButton = new QPushButton("撤回ROI点", box);
    auto* clearButton = new QPushButton("清空当前ROI", box);
    drawFlowRoiButton_->setCheckable(true);
    drawDetectRoiButton_->setCheckable(true);
    drawFlowRoiButton_->setChecked(true);
    buttons->addWidget(drawFlowRoiButton_);
    buttons->addWidget(drawDetectRoiButton_);
    buttons->addWidget(undoButton);
    buttons->addWidget(clearButton);

    layout->addLayout(form);
    layout->addWidget(help);
    layout->addLayout(buttons);

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
        previewLabel_->setFlowRoiFromText(flowRoiEdit_->text());
    });
    connect(detectRoiEdit_, &QLineEdit::editingFinished, this, [this]() {
        previewLabel_->setDetectRoiFromText(detectRoiEdit_->text());
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
    sourceEdit_->setText(settings.value("lastSourcePath", sourceEdit_->text()).toString());
    const QString savedOutput = settings.value("lastOutputDir", outputEdit_->text()).toString().trimmed();
    outputEdit_->setText(savedOutput.isEmpty() ? RuntimePaths::defaultOutputDir() : savedOutput);
    flowRoiEdit_->setText(settings.value("lastFlowRoi", flowRoiEdit_->text()).toString());
    detectRoiEdit_->setText(settings.value("lastDetectRoi", detectRoiEdit_->text()).toString());
    hikIpEdit_->setText(settings.value("hikvisionIp", hikIpEdit_->text()).toString());
    hikUserEdit_->setText(settings.value("hikvisionUser", hikUserEdit_->text()).toString());
    hikPasswordEdit_->setText(settings.value("hikvisionPassword", hikPasswordEdit_->text()).toString());
    hikChannelSpin_->setValue(settings.value("hikvisionChannel", hikChannelSpin_->value()).toInt());
    inputSizeSpin_->setValue(settings.value("inputSize", inputSizeSpin_->value()).toInt());
    videoFpsSpin_->setValue(settings.value("previewFps", videoFpsSpin_->value()).toInt());
    jamSecondsSpin_->setValue(settings.value("jamSeconds", jamSecondsSpin_->value()).toInt());
    confidenceSpin_->setValue(settings.value("confidence", confidenceSpin_->value()).toDouble());
    iouSpin_->setValue(settings.value("iou", iouSpin_->value()).toDouble());
    const QString savedDevice = settings.value("deviceMode", "auto").toString();
    const int deviceIndex = deviceCombo_->findData(savedDevice);
    deviceCombo_->setCurrentIndex(deviceIndex >= 0 ? deviceIndex : 0);
    previewLabel_->setFlowRoiFromText(flowRoiEdit_->text());
    previewLabel_->setDetectRoiFromText(detectRoiEdit_->text());
}

void MainWindow::saveSettings() const {
    QSettings settings;
    settings.setValue("lastModelPath", ptEdit_->text().trimmed());
    settings.setValue("lastSourcePath", sourceEdit_->text().trimmed());
    settings.setValue("lastOutputDir", outputEdit_->text().trimmed());
    settings.setValue("lastFlowRoi", flowRoiEdit_->text().trimmed());
    settings.setValue("lastDetectRoi", detectRoiEdit_->text().trimmed());
    settings.setValue("hikvisionIp", hikIpEdit_->text().trimmed());
    settings.setValue("hikvisionUser", hikUserEdit_->text().trimmed());
    settings.setValue("hikvisionPassword", hikPasswordEdit_->text());
    settings.setValue("hikvisionChannel", hikChannelSpin_->value());
    settings.setValue("inputSize", inputSizeSpin_->value());
    settings.setValue("previewFps", videoFpsSpin_->value());
    settings.setValue("jamSeconds", jamSecondsSpin_->value());
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

DetectJobConfig MainWindow::currentDetectConfig() const {
    const QString outputDir = outputEdit_->text().trimmed();
    return {
        ptEdit_->text().trimmed(),
        sourceEdit_->text().trimmed(),
        outputDir,
        RuntimePaths::workerExePath(),
        RuntimePaths::trackerConfigPath(),
        flowRoiEdit_->text().trimmed(),
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
    if (flowRoiEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少 ROI", "请先在右侧视频画面绘制至少3个点的流量 ROI。");
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

    saveSettings();
    refreshModelMetadata();
    workerThread_ = new QThread(this);
    worker_ = new DetectionWorker(currentDetectConfig());
    worker_->moveToThread(workerThread_);
    connect(workerThread_, &QThread::started, worker_, &DetectionWorker::run);
    connect(worker_, &DetectionWorker::frameReady, this, &MainWindow::showFrame);
    connect(worker_, &DetectionWorker::log, this, &MainWindow::appendLog);
    connect(worker_, &DetectionWorker::done, this, &MainWindow::detectionFinished);
    connect(worker_, &DetectionWorker::failed, this, &MainWindow::detectionFailed);
    connect(worker_, &DetectionWorker::done, workerThread_, &QThread::quit);
    connect(worker_, &DetectionWorker::failed, workerThread_, &QThread::quit);
    connect(workerThread_, &QThread::finished, this, &MainWindow::cleanupWorker);
    startButton_->setEnabled(false);
    stopButton_->setEnabled(true);
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

void MainWindow::appendLog(const QString& message) {
    const QString text = message.trimmed();
    if (!text.isEmpty()) {
        logEdit_->appendPlainText(QDateTime::currentDateTime().toString("HH:mm:ss ") + text);
    }
}

void MainWindow::refreshModelMetadata() {
    if (!QFileInfo::exists(RuntimePaths::workerExePath()) || !QFileInfo::exists(ptEdit_->text())) {
        loadedLabels_.clear();
        populateClassCombo({});
        return;
    }

    QProcess process;
    process.setProcessChannelMode(QProcess::MergedChannels);
    process.start(RuntimePaths::workerExePath(), inspectModelArgs(ptEdit_->text()));
    if (!process.waitForStarted(5000)) {
        appendLog("模型类别读取失败：worker 进程启动失败。");
        return;
    }
    process.waitForFinished(-1);
    const QByteArray output = process.readAllStandardOutput();
    if (process.exitCode() != 0) {
        appendLog("模型类别读取失败：" + QString::fromUtf8(output).trimmed());
        loadedLabels_.clear();
        populateClassCombo({});
        return;
    }

    loadedLabels_ = parseClassLabelsFromJson(output);
    populateClassCombo(loadedLabels_);
    if (!loadedLabels_.isEmpty()) {
        appendLog("已读取模型类别：" + loadedLabels_.join(", "));
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
    process.waitForFinished(30000);
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
    appendLog(summary);
}

void MainWindow::detectionFailed(const QString& error) {
    appendLog(error);
    QMessageBox::critical(this, "检测失败", error);
}

void MainWindow::cleanupWorker() {
    if (worker_ != nullptr) {
        worker_->deleteLater();
        worker_ = nullptr;
    }
    if (workerThread_ != nullptr) {
        workerThread_->deleteLater();
        workerThread_ = nullptr;
    }
    startButton_->setEnabled(true);
    stopButton_->setEnabled(false);
}

void MainWindow::loadVideoPreviewFrame() {
    const QString source = sourceEdit_->text().trimmed();
    if (source.isEmpty() || (!canBeRuntimeSource(source) && !QFileInfo::exists(source))) {
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
