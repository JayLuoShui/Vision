#include "MainWindow.h"
#include "RuntimePaths.h"

#include <openvino/openvino.hpp>
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
#include <QIntValidator>
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
#include <QPushButton>
#include <QRegularExpression>
#include <QPixmap>
#include <QResizeEvent>
#include <QScrollArea>
#include <QScrollBar>
#include <QSettings>
#include <QSignalBlocker>
#include <QSizePolicy>
#include <QSpinBox>
#include <QSplitter>
#include <QStyle>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTextCursor>
#include <QTextOption>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#include <QWheelEvent>

#include <algorithm>
#include <stdexcept>
#include <utility>
#include <vector>

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

QString privatePath(const QPlainTextEdit* edit) {
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

QString previewSourceLabel(const QString& source) {
    const QString trimmed = source.trimmed();
    if (!trimmed.contains("://")) {
        return privatePathLabel(trimmed);
    }

    const QUrl url(trimmed);
    QString host = url.host().isEmpty() ? "网络视频流" : url.host();
    if (url.port() > 0) {
        host += ":" + QString::number(url.port());
    }
    const QString path = url.path().isEmpty() ? QString() : " · " + url.path();
    return url.scheme().toUpper() + " · " + host + path;
}

void configureAdaptiveLineEdit(QLineEdit* edit, int minChars = 10, int maxChars = 28) {
    if (edit == nullptr) {
        return;
    }
    const QString configKey = QString::number(minChars) + ":" + QString::number(maxChars);
    if (edit->property("adaptiveWidthConfig").toString() == configKey) {
        return;
    }
    edit->setProperty("adaptiveWidthConfig", configKey);
    edit->setMinimumWidth(0);
    edit->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    auto updateWidth = [edit, minChars, maxChars]() {
        QString sample = edit->text().trimmed();
        if (sample.isEmpty()) {
            sample = edit->placeholderText().trimmed();
        }
        const int contentChars = static_cast<int>(sample.size()) + 1;
        const int targetChars = std::clamp(contentChars, minChars, maxChars);
        const int width = edit->fontMetrics().horizontalAdvance(QString(targetChars, QLatin1Char('8'))) + 28;
        edit->setMinimumWidth(width);
    };
    QObject::connect(edit, &QLineEdit::textChanged, edit, [updateWidth](const QString&) {
        updateWidth();
    });
    updateWidth();
}

void configureAdaptiveComboBox(QComboBox* combo, int minChars = 8) {
    if (combo == nullptr) {
        return;
    }
    combo->setMinimumWidth(0);
    combo->setMinimumContentsLength(minChars);
    combo->setSizeAdjustPolicy(QComboBox::AdjustToMinimumContentsLengthWithIcon);
    combo->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
}

void configureCompactField(QWidget* widget, int width = 150) {
    if (widget == nullptr) {
        return;
    }
    widget->setMinimumWidth(width);
    widget->setMaximumWidth(width);
    widget->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
}

QLabel* makeCompactParamLabel(const QString& text, QWidget* parent) {
    auto* label = new QLabel(text, parent);
    label->setObjectName("compactParamLabel");
    label->setFixedWidth(64);
    label->setMinimumHeight(24);
    label->setAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    return label;
}

void configureModelPathEdit(QPlainTextEdit* edit) {
    if (edit == nullptr) {
        return;
    }
    edit->setReadOnly(true);
    edit->setLineWrapMode(QPlainTextEdit::WidgetWidth);
    edit->setWordWrapMode(QTextOption::WrapAnywhere);
    edit->setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    edit->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    edit->setMinimumHeight(46);
    edit->setMaximumHeight(50);
    edit->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
}

void configurePortLineEdit(QLineEdit* edit) {
    if (edit == nullptr) {
        return;
    }
    edit->setValidator(new QIntValidator(1, 65535, edit));
    edit->setMaxLength(5);
    edit->setAlignment(Qt::AlignCenter);
    const int width = edit->fontMetrics().horizontalAdvance(QStringLiteral("65535")) + 28;
    edit->setMinimumWidth(width);
    edit->setFixedWidth(width);
    edit->setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
}

int checkedPortFromEdit(const QLineEdit* edit) {
    bool ok = false;
    const int port = edit == nullptr ? 0 : edit->text().trimmed().toInt(&ok);
    if (!ok || port < 1 || port > 65535) {
        throw std::runtime_error("海康 RTSP 端口必须是 1-65535。");
    }
    return port;
}

void normalizePortLineEdit(QLineEdit* edit) {
    if (edit == nullptr) {
        return;
    }
    try {
        edit->setText(QString::number(checkedPortFromEdit(edit)));
    } catch (const std::exception&) {
        edit->setText(QStringLiteral("554"));
    }
}

void configureAdaptiveForm(QFormLayout* form) {
    if (form == nullptr) {
        return;
    }
    form->setFieldGrowthPolicy(QFormLayout::ExpandingFieldsGrow);
    form->setRowWrapPolicy(QFormLayout::WrapLongRows);
    form->setFormAlignment(Qt::AlignLeft | Qt::AlignTop);
    form->setLabelAlignment(Qt::AlignLeft | Qt::AlignVCenter);
}

void setPrivatePath(QLineEdit* edit, const QString& path, bool revealFull = false) {
    if (edit == nullptr) {
        return;
    }
    const QString trimmed = path.trimmed();
    edit->setProperty("fullPath", trimmed);
    edit->setText(revealFull ? trimmed : privatePathLabel(trimmed));
    edit->setCursorPosition(0);
    configureAdaptiveLineEdit(edit, 12, 30);
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

void setPrivatePath(QPlainTextEdit* edit, const QString& path, bool revealFull = false) {
    if (edit == nullptr) {
        return;
    }
    const QString trimmed = path.trimmed();
    edit->setProperty("fullPath", trimmed);
    edit->setPlainText(revealFull ? trimmed : privatePathLabel(trimmed));
    QTextCursor cursor = edit->textCursor();
    cursor.movePosition(QTextCursor::Start);
    edit->setTextCursor(cursor);
    if (!revealFull || trimmed.isEmpty()) {
        return;
    }
    QTimer::singleShot(5000, edit, [edit, trimmed]() {
        if (privatePath(edit) == trimmed) {
            edit->setPlainText(privatePathLabel(trimmed));
            QTextCursor cursor = edit->textCursor();
            cursor.movePosition(QTextCursor::Start);
            edit->setTextCursor(cursor);
        }
    });
}

cv::VideoCapture openCapture(const QString& source, const QString& rtspTransport = "tcp") {
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
            cv::CAP_PROP_READ_TIMEOUT_MSEC, 3000
        };
        cv::VideoCapture capture(trimmed.toStdString(), cv::CAP_FFMPEG, params);
        if (capture.isOpened()) {
            capture.set(cv::CAP_PROP_BUFFERSIZE, 1);
        }
        return capture;
    }
    return cv::VideoCapture(trimmed.toStdString());
}

QString findDefaultModelPath() {
    const QDir weightsDir(RuntimePaths::defaultWeightsDir());
    const QStringList files = weightsDir.entryList({"*.xml"}, QDir::Files, QDir::Name);
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

QString resolveDefaultModelPath() {
    return findDefaultModelPath();
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

bool isAllCountRegionsId(const QString& regionId) {
    return regionId == QStringLiteral("__all_count_regions__");
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

QString statusToneForText(const QString& text, bool running) {
    if (text.contains("堵包") || text.contains("异常") || text.contains("失败")) {
        return "jam";
    }
    if (text.contains("已完成")) {
        return "completed";
    }
    if (running || text.contains("运行") || text.contains("启动") || text.contains("检测")) {
        return "running";
    }
    return "idle";
}

void applyStatusTone(QLabel* label, const QString& tone) {
    label->setProperty("status", tone);
    label->style()->unpolish(label);
    label->style()->polish(label);
    label->update();
}

QPoint polygonCenter(const QVector<QPoint>& polygon) {
    if (polygon.isEmpty()) {
        return {};
    }
    qint64 sumX = 0;
    qint64 sumY = 0;
    for (const QPoint& point : polygon) {
        sumX += point.x();
        sumY += point.y();
    }
    return QPoint(static_cast<int>(sumX / polygon.size()), static_cast<int>(sumY / polygon.size()));
}

bool mapRegionToCameraFrame(
    const RegionConfig& source,
    const QRect& cameraRect,
    const QSize& cameraSize,
    RegionConfig* mapped) {
    if (mapped == nullptr || cameraRect.isEmpty() || !cameraSize.isValid()) {
        return false;
    }
    if (!cameraRect.contains(polygonCenter(source.polygon))) {
        return false;
    }
    *mapped = source;
    mapped->polygon.clear();
    mapped->polygon.reserve(source.polygon.size());
    const double sx = static_cast<double>(cameraSize.width()) / std::max(1, cameraRect.width());
    const double sy = static_cast<double>(cameraSize.height()) / std::max(1, cameraRect.height());
    for (const QPoint& point : source.polygon) {
        const int x = std::clamp(static_cast<int>((point.x() - cameraRect.left()) * sx), 0, cameraSize.width() - 1);
        const int y = std::clamp(static_cast<int>((point.y() - cameraRect.top()) * sy), 0, cameraSize.height() - 1);
        mapped->polygon.push_back(QPoint(x, y));
    }
    return true;
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

    if (alertFlashVisible_ && !jamRegionIds_.isEmpty()) {
        painter.setPen(QPen(QColor("#F25555"), 4));
        painter.setBrush(Qt::NoBrush);
        painter.drawRect(rect().adjusted(2, 2, -2, -2));
    }
}

void RoiPreviewLabel::mousePressEvent(QMouseEvent* event) {
    if (image_.isNull()) {
        return;
    }
    if (event->button() == Qt::LeftButton) {
        emit imageClicked(labelToImagePoint(event->pos()));
    }
    if (!roiEditingEnabled_) {
        event->accept();
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

VideoPreviewWorker::VideoPreviewWorker(QString source, QString rtspTransport)
    : source_(std::move(source)),
      rtspTransport_(std::move(rtspTransport)) {}

void VideoPreviewWorker::run() {
    try {
        constexpr int previewIntervalMs = 33;
        cv::VideoCapture capture = openCapture(source_, rtspTransport_);
        if (!capture.isOpened()) {
            emit failed("无法打开视频源。");
            emit finished();
            return;
        }
        while (!stopped_) {
            cv::Mat frame;
            if (!capture.read(frame) || frame.empty()) {
                emit failed("视频流读取中断。");
                break;
            }
            if (canBeRuntimeSource(source_) && isLowInformationFrame(frame)) {
                QThread::msleep(previewIntervalMs);
                continue;
            }
            emit frameReady(matToImage(frame));
            QThread::msleep(previewIntervalMs);
        }
        capture.release();
    } catch (const std::exception& ex) {
        emit failed(QString::fromUtf8(ex.what()));
    }
    emit finished();
}

void VideoPreviewWorker::stop() {
    stopped_ = true;
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
    brandBar->setFixedHeight(52);
    auto* brandLayout = new QHBoxLayout(brandBar);
    brandLayout->setContentsMargins(10, 5, 10, 5);
    brandLayout->setSpacing(8);

    auto* brandLogo = new QLabel(brandBar);
    brandLogo->setObjectName("brandLogo");
    brandLogo->setFixedSize(32, 32);
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
    productTitle->setObjectName("AppTitle");
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
    settingsToggleButton_ = new QPushButton("^  收起控制面板", brandBar);
    settingsToggleButton_->setObjectName("topControlButton");
    settingsToggleButton_->setCheckable(true);
    settingsToggleButton_->setFixedWidth(120);
    settingsToggleButton_->setFixedHeight(40);
    connect(settingsToggleButton_, &QPushButton::toggled, this, [this](bool checked) {
        setSettingsPanelCollapsed(checked);
    });
    brandLayout->addWidget(settingsToggleButton_);
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
    leftShell->setMinimumWidth(320);
    leftShell->setMaximumWidth(320);
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
    sidebarSubtitle->setObjectName("SideSubtitle");
    sidebarHeaderLayout->addWidget(sidebarTitle);
    sidebarHeaderLayout->addWidget(sidebarSubtitle);
    leftLayout->addWidget(sidebarHeader);

    auto* sidebarNavigation = new QWidget(leftShell);
    sidebarNavigation->setObjectName("SideMenu");
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
    monitorLayout->setContentsMargins(0, 0, 0, 0);
    monitorLayout->setSpacing(0);
    auto* monitorHeader = new QFrame(monitorPanel);
    monitorHeader->setObjectName("monitorHeader");
    monitorHeader->setFixedHeight(34);
    auto* monitorHeaderLayout = new QHBoxLayout(monitorHeader);
    monitorHeaderLayout->setContentsMargins(10, 0, 10, 0);
    auto* monitorTitle = new QLabel("实时监控画面", monitorHeader);
    monitorTitle->setObjectName("PanelTitle");
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
    regionPanel->setMinimumHeight(46);
    regionPanel->setMaximumHeight(46);
    regionPanel->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Preferred);
    auto* regionPanelLayout = new QVBoxLayout(regionPanel);
    regionPanelLayout->setContentsMargins(0, 0, 0, 0);
    regionPanelLayout->setSpacing(0);
    auto* regionHeader = new QFrame(regionPanel);
    regionHeader->setObjectName("regionHeader");
    regionHeader->setFixedHeight(46);
    auto* regionHeaderLayout = new QHBoxLayout(regionHeader);
    regionHeaderLayout->setContentsMargins(10, 0, 6, 0);
    auto* regionTitle = new QLabel("区域统计详情", regionHeader);
    regionTitle->setObjectName("PanelTitle");
    regionHeaderLayout->addWidget(regionTitle);
    regionHeaderLayout->addStretch(1);

    regionDetailsToggleButton_ = new QPushButton("展开区域统计   ›", regionHeader);
    regionDetailsToggleButton_->setObjectName("footerToggleButton");
    regionDetailsToggleButton_->setCheckable(true);
    regionDetailsToggleButton_->setMaximumWidth(130);
    regionHeaderLayout->addWidget(regionDetailsToggleButton_);

    logToggleButton_ = new QPushButton("展开运行日志   ›", regionHeader);
    logToggleButton_->setObjectName("footerToggleButton");
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
    logEdit_->setMaximumBlockCount(800);
    logEdit_->setMinimumHeight(80);
    logEdit_->setMaximumHeight(120);
    logEdit_->setVisible(false);
    connect(logToggleButton_, &QPushButton::toggled, this, [this](bool checked) {
        logEdit_->setVisible(checked);
        logToggleButton_->setText(checked ? "收起运行日志   ‹" : "展开运行日志   ›");
    });
    connect(regionDetailsToggleButton_, &QPushButton::toggled, this, [this, regionPanel](bool checked) {
        regionDetailsContent_->setVisible(checked);
        regionDetailsToggleButton_->setText(checked ? "收起区域统计   ‹" : "展开区域统计   ›");
        regionPanel->setMinimumHeight(checked ? 170 : 46);
        regionPanel->setMaximumHeight(checked ? 220 : 46);
    });

    rightLayout->addWidget(monitorPanel, 1);
    rightLayout->addWidget(regionPanel);
    rightLayout->addWidget(logEdit_);

    splitter->addWidget(leftShell);
    splitter->addWidget(right);
    splitter->setStretchFactor(0, 0);
    splitter->setStretchFactor(1, 1);
    splitter->setSizes({320, 1040});
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

    QFile styleFile(":/styles/cvds.qss");
    if (!styleFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        throw std::runtime_error("无法加载内置界面样式 cvds.qss");
    }
    setStyleSheet(QString::fromUtf8(styleFile.readAll()));

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
    connect(previewLabel_, &RoiPreviewLabel::imageClicked, this, &MainWindow::selectCameraAtPoint);

    pipelineManager_ = new PipelineRuntimeManager(this);
    connect(pipelineManager_, &PipelineRuntimeManager::frameReady, this, [this](
        const QString& cameraId,
        const QImage& image
    ) {
        cameraFrames_[cameraId] = image;
        if (previewComposePending_) {
            return;
        }
        previewComposePending_ = true;
        QTimer::singleShot(100, this, [this]() {
            previewComposePending_ = false;
            composeMultiCameraPreview();
        });
    });
    connect(
        pipelineManager_,
        &PipelineRuntimeManager::dashboardPayloadReady,
        this,
        &MainWindow::updateDashboardForCamera
    );
    connect(pipelineManager_, &PipelineRuntimeManager::log, this, [this](
        const QString& cameraId,
        const QString& message
    ) {
        appendLog(QString("[%1] %2").arg(cameraId, message));
    });
    connect(pipelineManager_, &PipelineRuntimeManager::done, this, [this](
        const QString& cameraId,
        const QString& summary
    ) {
        appendLog(QString("[%1] %2").arg(cameraId, summary));
    });
    connect(pipelineManager_, &PipelineRuntimeManager::failed, this, [this](
        const QString& cameraId,
        const QString& error
    ) {
        appendLog(QString("[%1] 检测失败：%2").arg(cameraId, error));
    });
    connect(pipelineManager_, &PipelineRuntimeManager::allFinished, this, &MainWindow::cleanupWorker);

    appendLog("已启动 CVDS 在线包裹流量监测，版本：" + RuntimePaths::versionText());
    appendLog("纯 C++ OpenVINO Runtime 推理引擎已就绪。");
    populateClassCombo({});
    loadSettings();
    regions_.clear();
    detectRoiEdit_->clear();
    ensureDefaultRegion();
    refreshRegionSelectors();
    applyRegionSelection();
    refreshRegionTable();
    previewLabel_->setDetectRoiFromText({});
    refreshRuntimeOverview();
    appendLog("启动完成：ROI 已按本次会话清空，选择视频后即可绘制。");
}

MainWindow::~MainWindow() {
    saveSettings();
    stopVideoPreview();
    for (const PreviewRuntime& runtime : previewRuntimes_) {
        if (runtime.thread != nullptr) {
            runtime.thread->quit();
            runtime.thread->wait();
        }
    }
    previewRuntimes_.clear();
    previewThread_ = nullptr;
    previewWorker_ = nullptr;
    if (previewThread_ != nullptr) {
        previewThread_->quit();
        previewThread_->wait();
    }
    if (pipelineManager_ != nullptr) {
        pipelineManager_->stopAndWait();
    }
}

void MainWindow::resizeEvent(QResizeEvent* event) {
    QMainWindow::resizeEvent(event);
    QTimer::singleShot(0, this, [this]() {
        resizeSidebarToStitchRatio();
    });
}

void MainWindow::resizeSidebarToStitchRatio() {
    if (mainSplitter_ == nullptr || settingsPanel_ == nullptr || mainSplitter_->width() <= 0
        || settingsPanelCollapsed_) {
        return;
    }
    const int leftWidth = 320;
    mainSplitter_->setSizes({leftWidth, std::max(1, mainSplitter_->width() - leftWidth)});
    QFont font = settingsPanel_->font();
    font.setPixelSize(qBound(11, leftWidth / 26, 14));
    settingsPanel_->setFont(font);
}

void MainWindow::setSettingsPanelCollapsed(bool collapsed) {
    settingsPanelCollapsed_ = collapsed;
    if (settingsPanel_ != nullptr) {
        settingsPanel_->setVisible(!collapsed);
    }
    if (settingsToggleButton_ != nullptr) {
        const QSignalBlocker blocker(settingsToggleButton_);
        settingsToggleButton_->setChecked(collapsed);
        settingsToggleButton_->setText(collapsed ? "v  展开控制面板" : "^  收起控制面板");
    }
    if (!collapsed) {
        QTimer::singleShot(0, this, [this]() {
            resizeSidebarToStitchRatio();
        });
    }
}

void MainWindow::startVideoPreview() {
    try {
        pendingPreviewSources_ = configuredSourcePaths();
    } catch (const std::exception& ex) {
        QMessageBox::warning(this, "视频源配置错误", QString::fromUtf8(ex.what()));
        return;
    }
    pendingPreviewTransport_ =
        hikTransportCombo_ == nullptr ? "tcp" : hikTransportCombo_->currentData().toString();
    previewFrameAccepted_ = false;
    cameraFrames_.clear();
    if (pendingPreviewSources_.isEmpty()) {
        return;
    }
    if (previewThread_ != nullptr || !previewRuntimes_.isEmpty()) {
        for (const PreviewRuntime& runtime : previewRuntimes_) {
            if (runtime.worker != nullptr) {
                QMetaObject::invokeMethod(runtime.worker, "stop", Qt::DirectConnection);
            }
        }
        if (previewWorker_ != nullptr) {
            QMetaObject::invokeMethod(previewWorker_, "stop", Qt::DirectConnection);
        }
        appendLog("正在切换视频通道，旧视频流释放后将自动连接新通道。");
        return;
    }
    launchPendingVideoPreview();
}

void MainWindow::launchPendingVideoPreview() {
    if (previewThread_ != nullptr || !previewRuntimes_.isEmpty() || pendingPreviewSources_.isEmpty()) {
        return;
    }
    const QStringList sources = pendingPreviewSources_;
    const QString transport = pendingPreviewTransport_;
    pendingPreviewSources_.clear();
    pendingPreviewTransport_.clear();
    previewFrameAccepted_ = true;
    for (int index = 0; index < sources.size(); ++index) {
        const QString source = sources[index];
        const QString sourceLabel = previewSourceLabel(source);
        const QString cameraId = QString("camera_%1").arg(index + 1);
        auto* thread = new QThread(this);
        auto* worker = new VideoPreviewWorker(source, transport);
        worker->moveToThread(thread);

        PreviewRuntime runtime;
        runtime.cameraId = cameraId;
        runtime.thread = thread;
        runtime.worker = worker;
        previewRuntimes_.push_back(runtime);
        if (index == 0) {
            previewThread_ = thread;
            previewWorker_ = worker;
        }

        connect(thread, &QThread::started, worker, &VideoPreviewWorker::run);
        connect(worker, &VideoPreviewWorker::frameReady, this, [this, cameraId](const QImage& image) {
            if (!previewFrameAccepted_) {
                return;
            }
            cameraFrames_[cameraId] = image;
            if (previewComposePending_) {
                return;
            }
            previewComposePending_ = true;
            QTimer::singleShot(100, this, [this]() {
                previewComposePending_ = false;
                composeMultiCameraPreview();
            });
        });
        connect(worker, &VideoPreviewWorker::failed, this, [this, cameraId, sourceLabel](const QString& error) {
            appendLog(QString("[%1] 视频预览失败（%2）：%3").arg(cameraId, sourceLabel, error));
        });
        connect(worker, &VideoPreviewWorker::finished, thread, &QThread::quit);
        connect(thread, &QThread::finished, worker, &QObject::deleteLater);
        connect(thread, &QThread::finished, this, [this, thread]() {
            cleanupPreview(thread);
        });
    }
    for (const PreviewRuntime& runtime : previewRuntimes_) {
        runtime.thread->start();
    }
    appendLog(QString("实时视频预览已启动：%1 路，可在画面上绘制 ROI。").arg(sources.size()));
}

void MainWindow::stopVideoPreview() {
    pendingPreviewSources_.clear();
    pendingPreviewTransport_.clear();
    previewFrameAccepted_ = false;
    previewComposePending_ = false;
    for (const PreviewRuntime& runtime : previewRuntimes_) {
        if (runtime.worker != nullptr) {
            QMetaObject::invokeMethod(runtime.worker, "stop", Qt::DirectConnection);
        }
    }
    if (previewWorker_ != nullptr) {
        QMetaObject::invokeMethod(previewWorker_, "stop", Qt::DirectConnection);
    }
}

void MainWindow::cleanupPreview(QThread* thread) {
    for (int i = 0; i < previewRuntimes_.size(); ++i) {
        if (previewRuntimes_[i].thread == thread) {
            if (previewRuntimes_[i].worker == previewWorker_) {
                previewWorker_ = nullptr;
            }
            if (previewRuntimes_[i].thread != nullptr) {
                previewRuntimes_[i].thread->deleteLater();
            }
            previewRuntimes_.removeAt(i);
            break;
        }
    }
    if (previewThread_ == thread) {
        previewThread_ = previewRuntimes_.isEmpty() ? nullptr : previewRuntimes_.first().thread;
        previewWorker_ = previewRuntimes_.isEmpty() ? nullptr : previewRuntimes_.first().worker;
    }
    if (!previewRuntimes_.isEmpty()) {
        return;
    }
    previewThread_ = nullptr;
    previewWorker_ = nullptr;
    previewFrameAccepted_ = false;
    if (startDetectionAfterPreviewStops_) {
        startDetectionAfterPreviewStops_ = false;
        QTimer::singleShot(0, this, &MainWindow::startDetection);
        return;
    }
    QTimer::singleShot(0, this, [this]() {
        launchPendingVideoPreview();
    });
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
        QVector<int> channels;
        try {
            channels = configuredHikvisionChannels();
        } catch (const std::exception&) {
            channels.clear();
        }
        const int channel = hikChannelSpin_ == nullptr ? 0 : hikChannelSpin_->value();
        const QString streamName = hikStreamCombo_ == nullptr ? QString() : hikStreamCombo_->currentText();
        if (!channels.isEmpty()) {
            QStringList channelTexts;
            for (int item : channels) {
                channelTexts.push_back(QString::number(item));
            }
            channelStatusLabel_->setText(QString("多路通道 %1 · %2").arg(channelTexts.join(",")).arg(streamName));
        } else {
            channelStatusLabel_->setText(channel > 0 ? QString("通道 %1 · %2").arg(channel).arg(streamName) : "通道 --");
        }
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
    configureAdaptiveLineEdit(sourceEdit_, 12, 30);
    setPrivatePath(sourceEdit_, {});
    sourceEdit_->setMinimumWidth(0);
    sourceEdit_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
    sourceModeCombo_ = new ScrollSafeComboBox(box);
    sourceModeCombo_->addItem("本地文件", "file");
    sourceModeCombo_->addItem("视频流", "stream");
    configureAdaptiveComboBox(sourceModeCombo_, 10);
    configureCompactField(sourceModeCombo_, 150);
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

    multiSourceEdit_ = new QPlainTextEdit(box);
    multiSourceEdit_->setPlaceholderText("多路视频在线检测：每行一路本地视频或 RTSP 地址；留空则使用上方单路视频源。");
    multiSourceEdit_->setMaximumHeight(72);
    multiSourceEdit_->setLineWrapMode(QPlainTextEdit::WidgetWidth);
    multiSourceEdit_->setWordWrapMode(QTextOption::WrapAnywhere);
    multiSourceEdit_->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    multiSourceEdit_->setMinimumWidth(0);
    multiSourceEdit_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
    auto* localVideoButton = new QPushButton("应用本地视频", box);
    rootLayout->addWidget(new QLabel("多路视频源", box));
    rootLayout->addWidget(multiSourceEdit_);
    rootLayout->addWidget(localVideoButton);
    connect(localVideoButton, &QPushButton::clicked, this, &MainWindow::applyLocalVideoSources);

    streamSettingsWidget_ = new QWidget(box);
    auto* streamLayout = new QGridLayout(streamSettingsWidget_);
    streamLayout->setContentsMargins(0, 4, 0, 0);
    streamLayout->setColumnStretch(1, 1);
    hikIpEdit_ = new QLineEdit(box);
    hikUserEdit_ = new QLineEdit("admin", box);
    hikPasswordEdit_ = new QLineEdit(box);
    multiHikChannelEdit_ = new QLineEdit(box);
    hikChannelSpin_ = new ScrollSafeSpinBox(box);
    hikRtspPortEdit_ = new QLineEdit(box);
    hikStreamCombo_ = new ScrollSafeComboBox(box);
    hikTransportCombo_ = new ScrollSafeComboBox(box);
    hikPasswordEdit_->setEchoMode(QLineEdit::Password);
    hikIpEdit_->setPlaceholderText("192.168.1.64");
    hikPasswordEdit_->setPlaceholderText("海康相机密码");
    multiHikChannelEdit_->setPlaceholderText("多路检测填写：1,2,3；留空则使用上方单通道");
    configureAdaptiveLineEdit(hikIpEdit_, 12, 18);
    configureAdaptiveLineEdit(hikUserEdit_, 8, 16);
    configureAdaptiveLineEdit(hikPasswordEdit_, 10, 20);
    configureAdaptiveLineEdit(multiHikChannelEdit_, 10, 20);
    configurePortLineEdit(hikRtspPortEdit_);
    hikChannelSpin_->setMinimumWidth(0);
    hikChannelSpin_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    configureAdaptiveComboBox(hikStreamCombo_, 6);
    configureAdaptiveComboBox(hikTransportCombo_, 4);
    hikChannelSpin_->setRange(1, 999);
    hikChannelSpin_->setValue(1);
    hikRtspPortEdit_->setText(QStringLiteral("554"));
    connect(hikRtspPortEdit_, &QLineEdit::editingFinished, this, [this]() {
        normalizePortLineEdit(hikRtspPortEdit_);
    });
    hikStreamCombo_->addItem("主码流", 1);
    hikStreamCombo_->addItem("子码流", 2);
    hikTransportCombo_->addItem("TCP", "tcp");
    hikTransportCombo_->addItem("UDP", "udp");

    streamLayout->setColumnMinimumWidth(0, 72);
    streamLayout->setColumnStretch(0, 0);
    streamLayout->setColumnStretch(1, 1);
    streamLayout->addWidget(new QLabel("设备IP", box), 0, 0);
    streamLayout->addWidget(hikIpEdit_, 0, 1);
    streamLayout->addWidget(new QLabel("RTSP端口", box), 1, 0);
    streamLayout->addWidget(hikRtspPortEdit_, 1, 1);
    streamLayout->addWidget(new QLabel("登录账号", box), 2, 0);
    streamLayout->addWidget(hikUserEdit_, 2, 1);
    streamLayout->addWidget(new QLabel("登录密码", box), 3, 0);
    streamLayout->addWidget(hikPasswordEdit_, 3, 1);
    streamLayout->addWidget(new QLabel("通道", box), 4, 0);
    streamLayout->addWidget(hikChannelSpin_, 4, 1);
    streamLayout->addWidget(new QLabel("码流", box), 5, 0);
    streamLayout->addWidget(hikStreamCombo_, 5, 1);
    streamLayout->addWidget(new QLabel("多路通道", box), 6, 0);
    streamLayout->addWidget(multiHikChannelEdit_, 6, 1);
    streamLayout->addWidget(new QLabel("传输协议", box), 7, 0);
    streamLayout->addWidget(hikTransportCombo_, 7, 1);
    auto* streamButtons = new QHBoxLayout();
    auto* hikButton = new QPushButton("应用视频流", box);
    auto* testButton = new QPushButton("测试连接", box);
    connect(hikButton, &QPushButton::clicked, this, &MainWindow::applyHikvisionStream);
    connect(testButton, &QPushButton::clicked, this, &MainWindow::testVideoStream);
    streamButtons->addWidget(hikButton);
    streamButtons->addWidget(testButton);
    streamLayout->addLayout(streamButtons, 8, 0, 1, 2);
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
        if (!streamMode) {
            stopVideoPreview();
        }
        refreshRuntimeOverview();
        }
    );
    streamSettingsWidget_->setVisible(false);

    return box;
}

QWidget* MainWindow::buildParamPanel() {
    auto* box = new QGroupBox("推理参数");
    auto* grid = new QGridLayout(box);
    grid->setColumnMinimumWidth(0, 64);
    grid->setColumnStretch(0, 0);
    grid->setColumnStretch(1, 1);
    grid->setHorizontalSpacing(8);
    grid->setVerticalSpacing(7);
    modelEdit_ = new QPlainTextEdit(box);
    configureModelPathEdit(modelEdit_);
    configureCompactField(modelEdit_);
    setPrivatePath(modelEdit_, {});
    auto* modelButtons = new QWidget(box);
    configureCompactField(modelButtons);
    auto* modelButtonLayout = new QVBoxLayout(modelButtons);
    modelButtonLayout->setContentsMargins(0, 0, 0, 0);
    modelButtonLayout->setSpacing(6);
    auto* modelFileButton = new QPushButton("模型文件", modelButtons);
    auto* openVinoButton = new QPushButton("OpenVINO目录", modelButtons);
    configureCompactField(modelFileButton);
    configureCompactField(openVinoButton);
    connect(modelFileButton, &QPushButton::clicked, this, &MainWindow::browseModel);
    connect(openVinoButton, &QPushButton::clicked, this, &MainWindow::browseOpenVinoDirectory);
    modelButtonLayout->addWidget(modelFileButton);
    modelButtonLayout->addWidget(openVinoButton);
    classCombo_ = new ScrollSafeComboBox(box);
    classCombo_->addItem("全部类别", -1);
    configureAdaptiveComboBox(classCombo_, 8);
    configureCompactField(classCombo_);
    backendCombo_ = new ScrollSafeComboBox(box);
    backendCombo_->addItem("OpenVINO", "openvino");
    backendCombo_->addItem("TensorRT", "tensorrt");
    configureAdaptiveComboBox(backendCombo_, 10);
    configureCompactField(backendCombo_);
    deviceCombo_ = new ScrollSafeComboBox(box);
    refreshDeviceOptions("AUTO");
    configureAdaptiveComboBox(deviceCombo_, 10);
    configureCompactField(deviceCombo_);
    connect(backendCombo_, qOverload<int>(&QComboBox::currentIndexChanged), this, [this]() {
        refreshDeviceOptions();
        saveSettings();
    });
    inputSizeSpin_ = new ScrollSafeSpinBox(box);
    inputSizeSpin_->setRange(160, 1536);
    inputSizeSpin_->setSingleStep(32);
    inputSizeSpin_->setValue(960);
    configureCompactField(inputSizeSpin_);
    videoFpsSpin_ = new ScrollSafeSpinBox(box);
    videoFpsSpin_->setRange(1, 120);
    videoFpsSpin_->setSingleStep(5);
    videoFpsSpin_->setValue(60);
    configureCompactField(videoFpsSpin_);
    confidenceSpin_ = new ScrollSafeDoubleSpinBox(box);
    confidenceSpin_->setRange(0.01, 0.99);
    confidenceSpin_->setSingleStep(0.05);
    confidenceSpin_->setValue(0.25);
    configureCompactField(confidenceSpin_);
    iouSpin_ = new ScrollSafeDoubleSpinBox(box);
    iouSpin_->setRange(0.01, 0.99);
    iouSpin_->setSingleStep(0.05);
    iouSpin_->setValue(0.45);
    configureCompactField(iouSpin_);

    int row = 0;
    grid->addWidget(makeCompactParamLabel("视觉模型", box), row, 0);
    grid->addWidget(modelEdit_, row++, 1);
    grid->addWidget(makeCompactParamLabel("选择方式", box), row, 0);
    grid->addWidget(modelButtons, row++, 1);
    grid->addWidget(makeCompactParamLabel("推理后端", box), row, 0);
    grid->addWidget(backendCombo_, row++, 1);
    grid->addWidget(makeCompactParamLabel("类别", box), row, 0);
    grid->addWidget(classCombo_, row++, 1);
    grid->addWidget(makeCompactParamLabel("执行设备", box), row, 0);
    grid->addWidget(deviceCombo_, row++, 1);
    grid->addWidget(makeCompactParamLabel("输入尺寸", box), row, 0);
    grid->addWidget(inputSizeSpin_, row++, 1);
    grid->addWidget(makeCompactParamLabel("预览FPS", box), row, 0);
    grid->addWidget(videoFpsSpin_, row++, 1);
    grid->addWidget(makeCompactParamLabel("置信度", box), row, 0);
    grid->addWidget(confidenceSpin_, row++, 1);
    grid->addWidget(makeCompactParamLabel("NMS IoU", box), row, 0);
    grid->addWidget(iouSpin_, row, 1);
    return box;
}

QWidget* MainWindow::buildRoiPanel() {
    auto* box = new QGroupBox("流量监测");
    auto* layout = new QVBoxLayout(box);
    auto* form = new QFormLayout();
    configureAdaptiveForm(form);

    regionCombo_ = new ScrollSafeComboBox(box);
    totalCountRegionCombo_ = new ScrollSafeComboBox(box);
    regionNameEdit_ = new QLineEdit(box);
    flowRoiEdit_ = new QLineEdit(box);
    detectRoiEdit_ = new QLineEdit(box);
    configureAdaptiveComboBox(regionCombo_, 10);
    configureAdaptiveComboBox(totalCountRegionCombo_, 10);
    configureAdaptiveLineEdit(regionNameEdit_, 10, 22);
    configureAdaptiveLineEdit(flowRoiEdit_, 18, 32);
    configureAdaptiveLineEdit(detectRoiEdit_, 18, 32);
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
    form->addRow("计数口径", totalCountRegionCombo_);
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
        auto refreshKpiForCountScope = [this]() {
            if (isDetectionRunning()) {
                aggregateDashboardFromCameraStates();
                dashboardStatusText_ = dashboardStatusForStates(
                    dashboardRuntimeStates_, dashboardJamActive_, "运行中");
                setDashboardAlarmActive(dashboardJamActive_);
            }
            refreshRegionTable();
        };
        const QString selectedId = totalCountRegionCombo_->currentData().toString();
        const int selectedIndex = findRegionIndexById(selectedId);
        if (isAllCountRegionsId(selectedId)) {
            totalCountRegionId_ = selectedId;
            refreshKpiForCountScope();
            return;
        }
        if (selectedIndex >= 0 && !regions_[selectedIndex].countEnabled) {
            QMessageBox::warning(this, "计数口径错误", "计数口径必须参与累计。");
            const QSignalBlocker blocker(totalCountRegionCombo_);
            totalCountRegionCombo_->setCurrentIndex(totalCountRegionCombo_->findData(totalCountRegionId_));
            return;
        }
        totalCountRegionId_ = selectedId;
        refreshKpiForCountScope();
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
                QMessageBox::warning(this, "计数口径错误", "计数口径必须参与累计。");
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
    auto* layout = new QGridLayout(box);
    layout->setColumnMinimumWidth(0, 72);
    layout->setColumnStretch(0, 0);
    layout->setColumnStretch(1, 1);
    layout->setHorizontalSpacing(8);
    layout->setVerticalSpacing(8);
    outputEdit_ = new QLineEdit(box);
    outputEdit_->setReadOnly(true);
    configureCompactField(outputEdit_);
    setPrivatePath(outputEdit_, RuntimePaths::defaultOutputDir());
    auto* outputButton = new QPushButton("选择输出目录", box);
    configureCompactField(outputButton);
    connect(outputButton, &QPushButton::clicked, this, &MainWindow::browseOutput);
    diagnoseButton_ = new QPushButton("运行环境自检", box);
    configureCompactField(diagnoseButton_);
    connect(diagnoseButton_, &QPushButton::clicked, this, &MainWindow::runEnvironmentDiagnose);
    layout->addWidget(new QLabel("输出目录", box), 0, 0);
    layout->addWidget(outputEdit_, 0, 1);
    layout->addWidget(outputButton, 1, 1);
    layout->addWidget(diagnoseButton_, 2, 1);
    return box;
}

QPushButton* MainWindow::buildSidebarNavigationButton(
    const QString& text,
    QWidget* panel,
    QWidget* parent
) {
    auto* button = new QPushButton(text, parent);
    button->setObjectName("navButton");
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
    box->setFixedHeight(94);
    box->setMinimumWidth(0);
    box->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
    auto* layout = new QHBoxLayout(box);
    layout->setSizeConstraint(QLayout::SetNoConstraint);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(4);

    auto buildCard = [box](
        const QString& title,
        const QString& valueObjectName,
        QLabel** valueLabel
    ) {
        auto* card = new QFrame(box);
        card->setObjectName("dashboardCard");
        card->setMinimumWidth(0);
        card->setFixedHeight(94);
        card->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        auto* cardLayout = new QVBoxLayout(card);
        cardLayout->setSizeConstraint(QLayout::SetNoConstraint);
        cardLayout->setContentsMargins(12, 7, 12, 7);
        cardLayout->setSpacing(1);
        auto* titleLabel = new QLabel(title, card);
        titleLabel->setObjectName("KpiTitle");
        titleLabel->setMinimumWidth(0);
        titleLabel->setAlignment(Qt::AlignCenter);
        titleLabel->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);
        *valueLabel = new QLabel("0", card);
        (*valueLabel)->setObjectName(valueObjectName);
        (*valueLabel)->setMinimumWidth(0);
        (*valueLabel)->setAlignment(Qt::AlignCenter);
        (*valueLabel)->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Preferred);
        cardLayout->addStretch(1);
        cardLayout->addWidget(titleLabel);
        cardLayout->addWidget(*valueLabel);
        cardLayout->addStretch(1);
        return card;
    };

    layout->addWidget(buildCard("累计包裹", "KpiValue", &kpiTotalCountValueLabel_), 1);
    layout->addWidget(buildCard("系统状态", "KpiStatusMain", &kpiStatusValueLabel_), 1);
    layout->addWidget(buildCard("当前区域状态", "KpiStatusMain", &kpiRegionStatusValueLabel_), 1);
    layout->addWidget(buildCard("堵包次数", "KpiValue", &kpiJamCountValueLabel_), 1);
    return box;
}

QString MainWindow::buildHikvisionRtsp() const {
    return buildHikvisionRtsp(hikChannelSpin_->value());
}

QString MainWindow::buildHikvisionRtsp(int channel) const {
    QUrl url;
    url.setScheme("rtsp");
    url.setHost(hikIpEdit_->text().trimmed());
    url.setPort(checkedPortFromEdit(hikRtspPortEdit_));
    url.setUserName(hikUserEdit_->text().trimmed());
    url.setPassword(hikPasswordEdit_->text());
    const int streamId = channel * 100 + hikStreamCombo_->currentData().toInt();
    url.setPath("/Streaming/Channels/" + QString::number(streamId));
    return url.toString(QUrl::FullyEncoded);
}

void MainWindow::loadSettings() {
    QSettings settings;
    const QString savedModel = settings.value("lastModelPath").toString();
    setPrivatePath(modelEdit_, QFileInfo::exists(savedModel) ? savedModel : QString());
    setPrivatePath(sourceEdit_, {});
    if (multiSourceEdit_ != nullptr) {
        multiSourceEdit_->clear();
    }
    const QString savedOutput = settings.value("lastOutputDir", privatePath(outputEdit_)).toString().trimmed();
    setPrivatePath(outputEdit_, savedOutput.isEmpty() ? RuntimePaths::defaultOutputDir() : savedOutput);
    settings.remove("lastDetectRoi");
    detectRoiEdit_->clear();
    hikIpEdit_->setText(settings.value("hikvisionIp", hikIpEdit_->text()).toString());
    hikUserEdit_->setText(settings.value("hikvisionUser", hikUserEdit_->text()).toString());
    hikPasswordEdit_->setText(settings.value("hikvisionPassword").toString());
    hikChannelSpin_->setValue(settings.value("hikvisionChannel", hikChannelSpin_->value()).toInt());
    if (multiHikChannelEdit_ != nullptr) {
        multiHikChannelEdit_->setText(settings.value("hikvisionMultiChannels").toString());
    }
    const int savedRtspPort = settings.value("hikvisionRtspPort", hikRtspPortEdit_->text()).toInt();
    hikRtspPortEdit_->setText(QString::number(std::clamp(savedRtspPort, 1, 65535)));
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
    const QString savedBackend = settings.value("inferenceBackend", "openvino").toString();
    const int backendIndex = backendCombo_->findData(savedBackend);
    backendCombo_->setCurrentIndex(backendIndex >= 0 ? backendIndex : 0);
    const QString savedDevice = settings.value("deviceMode", "AUTO").toString();
    refreshDeviceOptions(savedDevice);
}

void MainWindow::saveSettings() const {
    QSettings settings;
    settings.setValue("lastModelPath", privatePath(modelEdit_));
    settings.remove("lastSourcePath");
    settings.remove("multiSourcePaths");
    settings.setValue("lastOutputDir", privatePath(outputEdit_));
    settings.remove("lastDetectRoi");
    settings.setValue("hikvisionIp", hikIpEdit_->text().trimmed());
    settings.setValue("hikvisionUser", hikUserEdit_->text().trimmed());
    settings.setValue("hikvisionPassword", hikPasswordEdit_->text());
    settings.setValue("hikvisionChannel", hikChannelSpin_->value());
    if (multiHikChannelEdit_ != nullptr) {
        settings.setValue("hikvisionMultiChannels", multiHikChannelEdit_->text().trimmed());
    }
    bool portOk = false;
    const int port = hikRtspPortEdit_ == nullptr ? 554 : hikRtspPortEdit_->text().trimmed().toInt(&portOk);
    settings.setValue("hikvisionRtspPort", portOk && port >= 1 && port <= 65535 ? port : 554);
    settings.setValue("hikvisionStream", hikStreamCombo_->currentData().toInt());
    settings.setValue("hikvisionTransport", hikTransportCombo_->currentData().toString());
    settings.setValue("sourceMode", sourceModeCombo_->currentData().toString());
    settings.setValue("inputSize", inputSizeSpin_->value());
    settings.setValue("previewFps", videoFpsSpin_->value());
    settings.setValue("confidence", confidenceSpin_->value());
    settings.setValue("iou", iouSpin_->value());
    settings.setValue("inferenceBackend", backendCombo_->currentData().toString());
    settings.setValue("deviceMode", deviceCombo_->currentData().toString());
}

void MainWindow::refreshDeviceOptions(const QString& preferredDevice) {
    if (backendCombo_ == nullptr || deviceCombo_ == nullptr) {
        return;
    }
    const QString backend = backendCombo_->currentData().toString().trimmed().toLower();
    const QString previous = preferredDevice.trimmed().isEmpty()
        ? deviceCombo_->currentData().toString()
        : preferredDevice.trimmed();

    const QSignalBlocker blocker(deviceCombo_);
    deviceCombo_->clear();
    if (backend == "tensorrt") {
        deviceCombo_->addItem("NVIDIA CUDA GPU 0", "0");
    } else {
        deviceCombo_->addItem("AUTO", "AUTO");
        deviceCombo_->addItem("CPU", "CPU");
        deviceCombo_->addItem("OpenVINO GPU（Intel）", "GPU");
    }

    int index = deviceCombo_->findData(previous);
    if (index < 0 && backend == "tensorrt" && previous.compare("CUDA", Qt::CaseInsensitive) == 0) {
        index = deviceCombo_->findData("0");
    }
    if (index < 0) {
        index = 0;
    }
    deviceCombo_->setCurrentIndex(index);
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
    region.id = "region_1";
    region.name = "区域 1";
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
        if (!isAllCountRegionsId(totalCountRegionId_)) {
            totalCountRegionId_ = regions_.first().id;
        }
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
        totalCountRegionCombo_->addItem("多区域汇总", QStringLiteral("__all_count_regions__"));
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
    if (isDetectionRunning()) {
        aggregateDashboardFromCameraStates();
        dashboardStatusText_ = dashboardStatusForStates(
            dashboardRuntimeStates_, dashboardJamActive_, "运行中");
        setDashboardAlarmActive(dashboardJamActive_);
    }
    refreshRegionTable();
}

void MainWindow::refreshRegionTable() {
    if (regionTable_ == nullptr) {
        return;
    }
    const int runtimeRowCount = isDetectionRunning() && !regionRuntimeStates_.isEmpty()
        ? regionRuntimeStates_.size()
        : 0;
    bool hasConfiguredRegion = false;
    for (const RegionConfig& region : regions_) {
        if (region.polygonClosed && region.polygon.size() >= 3) {
            hasConfiguredRegion = true;
            break;
        }
    }
    const int displayRowCount = runtimeRowCount > 0 ? runtimeRowCount : (hasConfiguredRegion ? regions_.size() : 0);
    regionTable_->setRowCount(displayRowCount);
    if (regionEmptyLabel_ != nullptr) {
        regionEmptyLabel_->setVisible(!hasConfiguredRegion);
    }
    QStringList jamIds;
    for (const RegionRuntimeState& state : regionRuntimeStates_) {
        if (state.jamActive) {
            jamIds.push_back(state.id);
        }
    }
    const bool alertVisible = dashboardJamActive_ && dashboardFlashVisible_;

    for (int row = 0; row < regionTable_->rowCount(); ++row) {
        const bool runtimeRow = runtimeRowCount > 0;
        const RegionConfig region = runtimeRow ? RegionConfig{} : regions_[row];
        RegionRuntimeState state = runtimeRow ? regionRuntimeStates_[row] : buildFallbackState(region);
        if (!runtimeRow) {
            for (const RegionRuntimeState& item : regionRuntimeStates_) {
                if (item.id == region.id) {
                    state = item;
                    break;
                }
            }
            if (state.name.trimmed().isEmpty()) {
                state.name = region.name;
            }
        }

        const QString statusText = regionStatusText(state, isDetectionRunning());
        const QString regionName = runtimeRow ? state.name : region.name;
        const bool isKpiRegion = state.id == (currentRegionId_.trimmed().isEmpty()
            ? totalCountRegionId_
            : currentRegionId_);
        const QString regionText = isKpiRegion
            ? regionName + "（当前看板）"
            : regionName;
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
            if (state.jamActive && alertVisible) {
                item->setBackground(QColor("#4A2024"));
            } else if (state.id == currentRegionId_) {
                item->setBackground(QColor("#172431"));
            } else {
                item->setBackground(QColor("#0B1118"));
            }
        }
    }

    previewLabel_->setJamRegionIds(jamIds);
    previewLabel_->setAlertFlashVisible(alertVisible);
    kpiTotalCountValueLabel_->setText(QString::number(dashboardTotalCount_));
    kpiStatusValueLabel_->setText(dashboardStatusText_);
    kpiJamCountValueLabel_->setText(QString::number(dashboardJamCount_));
    applyStatusTone(
        kpiStatusValueLabel_,
        statusToneForText(dashboardStatusText_, isDetectionRunning())
    );

    QStringList regionStatusLines;
    QString regionStatusTone = "idle";
    auto appendRegionStatus = [&](const RegionRuntimeState& state) {
        const QString statusText = regionStatusText(state, isDetectionRunning());
        const QString regionName = state.name.trimmed().isEmpty() ? state.id : state.name;
        regionStatusLines.push_back(regionName + " " + statusText);
        const QString tone = statusToneForText(statusText, isDetectionRunning());
        if (tone == "jam" || (tone == "running" && regionStatusTone != "jam")) {
            regionStatusTone = tone;
        }
    };
    if (!regionRuntimeStates_.isEmpty()) {
        for (const RegionRuntimeState& state : regionRuntimeStates_) {
            appendRegionStatus(state);
        }
    } else {
        for (const RegionConfig& region : regions_) {
            appendRegionStatus(buildFallbackState(region));
        }
    }
    if (regionStatusLines.isEmpty()) {
        regionStatusLines.push_back("未配置区域");
    }
    kpiRegionStatusValueLabel_->setText(regionStatusLines.join('\n'));
    applyStatusTone(kpiRegionStatusValueLabel_, regionStatusTone);

    if (systemStatusLabel_ != nullptr) {
        if (dashboardJamActive_) {
            systemStatusLabel_->setText("●  堵包告警");
            applyStatusTone(systemStatusLabel_, "jam");
        } else if (isDetectionRunning()) {
            systemStatusLabel_->setText("●  正在监测");
            applyStatusTone(systemStatusLabel_, "running");
        } else {
            systemStatusLabel_->setText("●  系统就绪");
            applyStatusTone(systemStatusLabel_, "idle");
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

RegionConfigDocument MainWindow::regionDocumentForCamera(const QString& cameraId, bool multiCamera) const {
    if (!multiCamera) {
        return buildRegionConfigDocument();
    }

    RegionConfigDocument document;
    document.version = 1;
    document.totalCountRegionId = totalCountRegionId_;
    const QRect cameraRect = cameraImageRects_.value(cameraId);
    const QSize cameraSize = cameraSourceSizes_.value(cameraId);
    QStringList regionIds;
    for (const RegionConfig& region : regions_) {
        if (!region.polygonClosed || region.polygon.size() < 3) {
            continue;
        }
        RegionConfig mapped;
        if (mapRegionToCameraFrame(region, cameraRect, cameraSize, &mapped)) {
            regionIds.push_back(mapped.id);
            document.regions.push_back(mapped);
        }
    }
    if (!document.regions.isEmpty() && !regionIds.contains(document.totalCountRegionId)) {
        document.totalCountRegionId = QStringLiteral("__all_count_regions__");
    }
    return document;
}

void MainWindow::restoreRegionConfigDocument(const RegionConfigDocument& document) {
    setDashboardAlarmActive(false);
    regionRuntimeStates_.clear();
    dashboardRuntimeStates_.clear();
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
    const bool tensorRt = backendCombo_ != nullptr
        && backendCombo_->currentData().toString().compare("tensorrt", Qt::CaseInsensitive) == 0;
    const QString path = QFileDialog::getOpenFileName(
        this,
        "选择视觉模型",
        privatePath(modelEdit_),
        tensorRt ? "TensorRT Engine (*.engine *.plan)" : "OpenVINO IR (*.xml)"
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
        stopVideoPreview();
        sourceModeCombo_->setCurrentIndex(sourceModeCombo_->findData("file"));
        sourceEdit_->setProperty("fullPath", path.trimmed());
        sourceEdit_->setText("已加入多路视频源");
        sourceEdit_->setCursorPosition(0);
        sourceEdit_->setMinimumWidth(0);
        sourceEdit_->setSizePolicy(QSizePolicy::Ignored, QSizePolicy::Fixed);
        multiSourceEdit_->appendPlainText(path);
        loadVideoPreviewFrame();
        refreshRuntimeOverview();
        saveSettings();
    }
}

void MainWindow::applyLocalVideoSources() {
    sourceModeCombo_->setCurrentIndex(sourceModeCombo_->findData("file"));
    const QStringList sources = configuredSourcePaths();
    if (sources.isEmpty()) {
        QMessageBox::warning(this, "缺少本地视频", "请先选择本地视频，或在多路视频源中每行填写一个视频路径。");
        return;
    }
    setDashboardAlarmActive(false);
    regions_.clear();
    detectRoiEdit_->clear();
    previewLabel_->setDetectRoiFromText({});
    ensureDefaultRegion();
    refreshRegionSelectors();
    applyRegionSelection();
    refreshRegionTable();
    refreshRuntimeOverview();
    saveSettings();
    appendLog(QString("已应用本地视频源：%1 路。").arg(sources.size()));
    loadConfiguredVideoPreviewFrames(sources);
}

void MainWindow::applyHikvisionStream() {
    if (hikIpEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少海康地址", "请先填写海康相机 IP 地址。");
        return;
    }
    sourceModeCombo_->setCurrentIndex(sourceModeCombo_->findData("stream"));
    QVector<int> channels;
    try {
        channels = configuredHikvisionChannels();
    } catch (const std::exception& ex) {
        QMessageBox::warning(this, "视频源配置错误", QString::fromUtf8(ex.what()));
        return;
    }
    try {
        setPrivatePath(sourceEdit_, channels.isEmpty() ? buildHikvisionRtsp() : buildHikvisionRtsp(channels.first()));
    } catch (const std::exception& ex) {
        QMessageBox::warning(this, "视频源配置错误", QString::fromUtf8(ex.what()));
        return;
    }
    refreshRuntimeOverview();
    saveSettings();
    appendLog(channels.isEmpty()
        ? "已应用海康视频流配置。"
        : QString("已应用海康多路通道：%1。").arg(multiHikChannelEdit_->text().trimmed()));
    startVideoPreview();
}

void MainWindow::testVideoStream() {
    if (hikIpEdit_->text().trimmed().isEmpty()) {
        QMessageBox::warning(this, "缺少海康地址", "请先填写海康设备 IP 地址。");
        return;
    }
    applyHikvisionStream();
    appendLog("正在通过实时预览测试海康视频流，连接失败会在运行日志中明确显示。");
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
            QMessageBox::warning(this, "无法删除", "没有可作为计数口径的区域，请先启用其他区域的累计。");
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

VideoPipeline::Config MainWindow::currentDetectConfig() const {
    VideoPipeline::Config config;
    config.modelPath = privatePath(modelEdit_);
    config.sourcePath = privatePath(sourceEdit_);
    config.rtspTransport = hikTransportCombo_->currentData().toString();
    config.outputDir = privatePath(outputEdit_);
    config.regions = buildRegionConfigDocument();
    config.detectRoi = polygonFromText(detectRoiEdit_->text(), "检测区域", true);
    config.labels = loadedLabels_;
    config.backend = inferenceBackendFromString(backendCombo_->currentData().toString());
    config.classFilterId = classCombo_->currentData().toInt();
    config.inputSize = inputSizeSpin_->value();
    config.confidence = confidenceSpin_->value();
    config.iou = iouSpin_->value();
    config.device = deviceCombo_->currentData().toString();
    config.previewFps = videoFpsSpin_->value();
    config.lowSpeedThreshold = 12.0;
    return config;
}

QStringList MainWindow::configuredSourcePaths() const {
    QStringList sources;
    if (multiSourceEdit_ != nullptr) {
        const QStringList lines = multiSourceEdit_->toPlainText().split(QRegularExpression("[\\r\\n]+"));
        for (const QString& line : lines) {
            const QString source = line.trimmed();
            if (!source.isEmpty() && !source.startsWith("#")) {
                sources.push_back(source);
            }
        }
    }
    const bool streamMode = sourceModeCombo_ != nullptr
        && sourceModeCombo_->currentData().toString() == "stream";
    if (streamMode) {
        if (hikPasswordEdit_ != nullptr && hikPasswordEdit_->text().isEmpty()) {
            throw std::runtime_error("海康密码不能为空，请先输入密码后再应用视频流。");
        }
        const QVector<int> channels = configuredHikvisionChannels();
        if (channels.isEmpty()) {
            sources.push_back(buildHikvisionRtsp());
        } else {
            for (int channel : channels) {
                sources.push_back(buildHikvisionRtsp(channel));
            }
        }
        sources.removeDuplicates();
        return sources;
    }
    if (sources.isEmpty()) {
        const QString source = privatePath(sourceEdit_).trimmed();
        if (!source.isEmpty()) {
            sources.push_back(source);
        }
    }
    sources.removeDuplicates();
    return sources;
}

QVector<int> MainWindow::configuredHikvisionChannels() const {
    QVector<int> channels;
    if (multiHikChannelEdit_ == nullptr) {
        return channels;
    }
    const QString text = multiHikChannelEdit_->text().trimmed();
    if (text.isEmpty()) {
        return channels;
    }
    const QStringList tokens = text.split(QRegularExpression("[,，;；\\s]+"), Qt::SkipEmptyParts);
    for (const QString& token : tokens) {
        const int channel = token.toInt();
        if (channel <= 0 || QString::number(channel) != token.trimmed()) {
            throw std::runtime_error(QString("海康多路通道必须是正整数：%1").arg(token).toUtf8().constData());
        }
        if (!channels.contains(channel)) {
            channels.push_back(channel);
        }
    }
    return channels;
}

bool MainWindow::startConfiguredPipelines(const QStringList& sources) {
    cameraFrames_.clear();

    const bool multiCamera = sources.size() > 1;
    if (multiCamera) {
        const QString rootOutputDir = privatePath(outputEdit_);
        for (int index = 0; index < sources.size(); ++index) {
            const QString cameraId = QString("camera_%1").arg(index + 1);
            if (!cameraImageRects_.contains(cameraId) || !cameraSourceSizes_.contains(cameraId)) {
                QMessageBox::warning(
                    this,
                    "多路 ROI 尚未完成画面归属",
                    "请先点击“应用视频流”，等待多路预览画面稳定显示后再绘制 ROI 并开始检测。");
                return false;
            }
            const QString cameraOutputDir = QDir(rootOutputDir).filePath(QString("camera_%1").arg(index + 1));
            if (!QDir().mkpath(cameraOutputDir)) {
                QMessageBox::warning(this, "输出目录不可写", "无法创建多路输出目录：" + cameraOutputDir);
                return false;
            }
        }
    }

    QVector<PipelineStartRequest> requests;
    requests.reserve(sources.size());
    for (int index = 0; index < sources.size(); ++index) {
        VideoPipeline::Config config = currentDetectConfig();
        config.sourcePath = sources[index];
        const QString cameraId = QString("camera_%1").arg(index + 1);
        config.regions = regionDocumentForCamera(cameraId, multiCamera);
        if (multiCamera) {
            config.outputDir = QDir(config.outputDir).filePath(QString("camera_%1").arg(index + 1));
        }
        requests.push_back({cameraId, config});
    }

    QString error;
    if (pipelineManager_ == nullptr || !pipelineManager_->start(requests, &error)) {
        QMessageBox::warning(this, "启动失败", error.isEmpty() ? "无法启动检测任务。" : error);
        return false;
    }

    startButton_->setEnabled(false);
    stopButton_->setEnabled(true);
    setConfigurationEditingEnabled(false);
    setSettingsPanelCollapsed(true);
    appendLog(QString("已启动 %1 路视频在线检测。").arg(sources.size()));
    return true;
}

void MainWindow::startDetection() {
    if (isDetectionRunning()) {
        QMessageBox::information(this, "任务运行中", "检测正在运行。");
        return;
    }
    if (privatePath(modelEdit_).trimmed().isEmpty()) {
        const QString defaultModelPath = resolveDefaultModelPath();
        if (!defaultModelPath.isEmpty()) {
            setPrivatePath(modelEdit_, defaultModelPath);
            appendLog("已自动选择默认模型：" + QFileInfo(defaultModelPath).fileName());
        }
    }
    if (!QFileInfo::exists(privatePath(modelEdit_))) {
        const QString backendName = backendCombo_ == nullptr ? "OpenVINO" : backendCombo_->currentText();
        QMessageBox::warning(this, "缺少模型", "请先选择 " + backendName + " 模型文件或模型目录。");
        return;
    }
    QStringList sources;
    try {
        sources = configuredSourcePaths();
    } catch (const std::exception& ex) {
        QMessageBox::warning(this, "视频源配置错误", QString::fromUtf8(ex.what()));
        return;
    }
    if (sources.isEmpty()) {
        QMessageBox::warning(this, "缺少视频源", "请先选择或填写视频源。");
        return;
    }
    for (const QString& source : sources) {
        if (!canBeRuntimeSource(source) && !QFileInfo::exists(source)) {
            QMessageBox::warning(this, "视频源不存在", "视频源不是本地文件、摄像头编号或网络流：" + source);
            return;
        }
    }
    QString outputError;
    if (!isOutputDirWritable(privatePath(outputEdit_), &outputError)) {
        QMessageBox::warning(this, "输出目录不可写", outputError);
        return;
    }
    if (previewThread_ != nullptr || !previewRuntimes_.isEmpty()) {
        startDetectionAfterPreviewStops_ = true;
        stopVideoPreview();
        appendLog("正在释放视频预览，完成后自动开始检测。");
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
    dashboardRuntimeStates_.clear();
    cameraRegionRuntimeStates_.clear();
    dashboardTotalCount_ = 0;
    dashboardInsideCount_ = 0;
    dashboardJamCount_ = 0;
    dashboardJamActive_ = false;
    dashboardFlashVisible_ = false;
    dashboardStatusText_ = "启动中";
    refreshRegionTable();

    refreshRegionTable();
    if (!startConfiguredPipelines(sources)) {
        cleanupWorker();
    }
}

void MainWindow::stopDetection() {
    if (pipelineManager_ != nullptr) {
        pipelineManager_->stop();
    }
}

void MainWindow::showFrame(const QImage& image) {
    previewLabel_->setImage(image);
}

void MainWindow::updateDashboard(const QByteArray& payload) {
    updateDashboardForCamera("camera_1", payload);
}

void MainWindow::updateDashboardForCamera(const QString& cameraId, const QByteArray& payload) {
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
        cameraRegionRuntimeStates_.insert(cameraId, states);
        aggregateDashboardFromCameraStates();
        const QString fallbackStatus = type == "done"
            ? QStringLiteral("已完成")
            : object.value("global_status").toString();
        dashboardStatusText_ = dashboardStatusForStates(dashboardRuntimeStates_, dashboardJamActive_, fallbackStatus);
        if (type == "done" && !dashboardJamActive_) {
            dashboardStatusText_ = "已完成";
        }
        setDashboardAlarmActive(dashboardJamActive_);
        refreshRegionTable();
    }

    if (type == "jam") {
        const bool isClear = eventType == "jam_cleared";
        QVector<RegionRuntimeState> states = cameraRegionRuntimeStates_.value(cameraId);
        if (object.contains("region_id")) {
            const QString regionId = object.value("region_id").toString();
            int stateIndex = -1;
            for (int i = 0; i < states.size(); ++i) {
                if (states[i].id == regionId) {
                    stateIndex = i;
                    break;
                }
            }
            if (stateIndex < 0) {
                RegionRuntimeState state;
                state.id = regionId;
                state.name = object.value("region_name").toString();
                states.push_back(state);
                stateIndex = states.size() - 1;
            }
            RegionRuntimeState& state = states[stateIndex];
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
            for (RegionRuntimeState& state : states) {
                state.jamActive = false;
                state.status = state.insideCount <= 0 ? "空闲" : "运行中";
            }
        }

        cameraRegionRuntimeStates_.insert(cameraId, states);
        aggregateDashboardFromCameraStates();
        dashboardStatusText_ = dashboardStatusForStates(dashboardRuntimeStates_, dashboardJamActive_, "运行中");
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
        QVector<RegionRuntimeState> states = cameraRegionRuntimeStates_.value(cameraId);
        for (RegionRuntimeState& state : states) {
            state.jamActive = false;
            state.insideCount = legacyInsideCount;
            state.status = state.insideCount <= 0 ? "空闲" : "运行中";
        }
        cameraRegionRuntimeStates_.insert(cameraId, states);
        aggregateDashboardFromCameraStates();
        dashboardStatusText_ = dashboardStatusForStates(dashboardRuntimeStates_, dashboardJamActive_, "运行中");
        setDashboardAlarmActive(dashboardJamActive_);
        refreshRegionTable();
        appendLog("堵包解除，信号 " + object.value("signal").toString());
    }
}

void MainWindow::aggregateDashboardFromCameraStates() {
    regionRuntimeStates_.clear();
    dashboardRuntimeStates_.clear();
    dashboardTotalCount_ = 0;
    dashboardInsideCount_ = 0;
    dashboardJamCount_ = 0;
    dashboardJamActive_ = false;

    const bool multiCameraRuntime = cameraRegionRuntimeStates_.size() > 1;
    QStringList allCameraIds = cameraRegionRuntimeStates_.keys();
    allCameraIds.sort();
    for (const QString& cameraId : allCameraIds) {
        const QVector<RegionRuntimeState> states = cameraRegionRuntimeStates_.value(cameraId);
        for (const RegionRuntimeState& state : states) {
            RegionRuntimeState displayState = state;
            if (multiCameraRuntime) {
                displayState.name = cameraId + " / "
                    + (displayState.name.trimmed().isEmpty() ? displayState.id : displayState.name);
            }
            regionRuntimeStates_.push_back(displayState);
        }
    }

    QStringList cameraIds = allCameraIds;
    cameraIds.sort();

    const QString kpiRegionId = totalCountRegionId_;

    for (const QString& cameraId : cameraIds) {
        const QVector<RegionRuntimeState> states = cameraRegionRuntimeStates_.value(cameraId);
        for (const RegionRuntimeState& state : states) {
            const bool stateMatchesKpiRegion = kpiRegionId == QStringLiteral("__all_count_regions__")
                || state.id == kpiRegionId;
            dashboardJamActive_ = dashboardJamActive_ || state.jamActive;
            if (!stateMatchesKpiRegion) {
                continue;
            }
            dashboardRuntimeStates_.push_back(state);
            dashboardJamCount_ += state.jamCount;
            dashboardTotalCount_ += state.flowCount;
            dashboardInsideCount_ += state.insideCount;
        }
    }
}

void MainWindow::selectCameraAtPoint(const QPoint& imagePoint) {
    QStringList cameraIds = cameraImageRects_.keys();
    cameraIds.sort();
    for (const QString& cameraId : cameraIds) {
        if (cameraImageRects_.value(cameraId).contains(imagePoint)) {
            if (!isDetectionRunning()) {
                selectDrawingRegionForCamera(cameraId);
                composeMultiCameraPreview();
            }
            return;
        }
    }
}

void MainWindow::selectDrawingRegionForCamera(const QString& cameraId) {
    const QRect cameraRect = cameraImageRects_.value(cameraId);
    if (cameraRect.isEmpty()) {
        return;
    }

    for (const RegionConfig& region : regions_) {
        if (!region.polygon.isEmpty() && cameraRect.contains(polygonCenter(region.polygon))) {
            currentRegionId_ = region.id;
            refreshRegionSelectors();
            applyRegionSelection();
            return;
        }
    }

    int emptyIndex = -1;
    for (int i = 0; i < regions_.size(); ++i) {
        if (regions_[i].polygon.isEmpty()) {
            emptyIndex = i;
            break;
        }
    }
    if (emptyIndex >= 0) {
        currentRegionId_ = regions_[emptyIndex].id;
        refreshRegionSelectors();
        applyRegionSelection();
        return;
    }

    RegionConfig region;
    region.id = nextRegionId();
    region.name = QString("区域 %1").arg(regions_.size() + 1);
    region.priority = regions_.size() + 1;
    regions_.push_back(region);
    currentRegionId_ = region.id;
    refreshRegionSelectors();
    applyRegionSelection();
}

bool MainWindow::isDetectionRunning() const {
    return pipelineManager_ != nullptr && pipelineManager_->isRunning();
}

void MainWindow::appendLog(const QString& message) {
    const QString text = message.trimmed();
    if (!text.isEmpty()) {
        logEdit_->appendPlainText(QDateTime::currentDateTime().toString("HH:mm:ss ") + text);
    }
}

void MainWindow::refreshModelMetadata() {
    const QString modelPath = privatePath(modelEdit_);
    if (!QFileInfo::exists(modelPath)) {
        loadedLabels_.clear();
        loadedModelPath_.clear();
        populateClassCombo({});
        return;
    }
    loadedModelPath_ = modelPath;
    loadedLabels_.clear();
    populateClassCombo({});
    const QString backendName = backendCombo_ == nullptr ? "OpenVINO" : backendCombo_->currentText();
    appendLog("已选择 " + backendName + " 模型：" + QFileInfo(modelPath).fileName());
}

void MainWindow::runEnvironmentDiagnose() {
    try {
        ov::Core core;
        const std::vector<std::string> devices = core.get_available_devices();
        QStringList names;
        for (const std::string& device : devices) {
            names.push_back(QString::fromStdString(device));
        }
        appendLog("环境自检：OpenVINO Runtime 正常。");
        appendLog("环境自检：可用设备 " + (names.isEmpty() ? QStringLiteral("CPU") : names.join(", ")));
#ifdef CVDS_WITH_TENSORRT
        appendLog("环境自检：TensorRT Runtime 已随程序编译启用，可加载 .engine/.plan。");
#else
        appendLog("环境自检：TensorRT Runtime 未随程序编译启用。");
#endif
        appendLog("环境自检：OpenCV 视频和图像模块已链接。");
    } catch (const std::exception& ex) {
        const QString error = QString::fromUtf8(ex.what());
        appendLog("环境自检失败：" + error);
        QMessageBox::critical(this, "环境自检失败", error);
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
    cameraFrames_.clear();
    cameraRegionRuntimeStates_.clear();
    regionRuntimeStates_.clear();
    dashboardRuntimeStates_.clear();
    previewComposePending_ = false;
    startButton_->setEnabled(true);
    stopButton_->setEnabled(false);
    setConfigurationEditingEnabled(true);
    refreshRuntimeOverview();
    refreshRegionTable();
}

void MainWindow::composeMultiCameraPreview() {
    if (cameraFrames_.isEmpty() || previewLabel_ == nullptr) {
        return;
    }
    QStringList cameraIds = cameraFrames_.keys();
    cameraIds.sort();
    if (cameraIds.size() == 1) {
        previewLabel_->setImage(cameraFrames_.value(cameraIds.first()));
        return;
    }

    const QSize cellSize(640, 360);
    const int columns = cameraIds.size() <= 2 ? cameraIds.size() : 2;
    const int rows = (cameraIds.size() + columns - 1) / columns;
    QImage canvas(cellSize.width() * columns, cellSize.height() * rows, QImage::Format_RGB888);
    canvas.fill(QColor("#080D13"));
    cameraImageRects_.clear();
    cameraSourceSizes_.clear();
    QPainter painter(&canvas);
    painter.setRenderHint(QPainter::SmoothPixmapTransform);
    for (int index = 0; index < cameraIds.size(); ++index) {
        const QString& cameraId = cameraIds[index];
        const QImage image = cameraFrames_.value(cameraId);
        const QRect cell(
            (index % columns) * cellSize.width(),
            (index / columns) * cellSize.height(),
            cellSize.width(),
            cellSize.height());
        const QImage scaled = image.scaled(cell.size(), Qt::KeepAspectRatio, Qt::SmoothTransformation);
        const QPoint topLeft(
            cell.left() + (cell.width() - scaled.width()) / 2,
            cell.top() + (cell.height() - scaled.height()) / 2);
        cameraImageRects_.insert(cameraId, QRect(topLeft, scaled.size()));
        cameraSourceSizes_.insert(cameraId, image.size());
        painter.drawImage(topLeft, scaled);
        painter.setPen(QPen(QColor("#263746"), 1));
        painter.drawRect(cell.adjusted(1, 1, -2, -2));
    }
    previewLabel_->setImage(canvas);
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
        previewLabel_->setJamRegionIds({});
    }
    previewLabel_->setAlertFlashVisible(dashboardFlashVisible_);
    updateAlertStyle();
}

void MainWindow::toggleAlarmFlash() {
    if (!dashboardJamActive_) {
        dashboardFlashVisible_ = false;
        previewLabel_->setJamRegionIds({});
        previewLabel_->setAlertFlashVisible(false);
        updateAlertStyle();
        refreshRegionTable();
        return;
    }
    dashboardFlashVisible_ = !dashboardFlashVisible_;
    previewLabel_->setAlertFlashVisible(dashboardFlashVisible_);
    updateAlertStyle();
    refreshRegionTable();
}

void MainWindow::updateAlertStyle() {
    if (dashboardRoot_ == nullptr) {
        return;
    }
    if (!dashboardJamActive_ || !dashboardFlashVisible_) {
        dashboardRoot_->setStyleSheet(
            "QWidget#dashboardRoot QFrame#monitorPanel{background:#080D13;border:1px solid #263746;border-radius:3px;}"
            "QWidget#dashboardRoot QFrame#dashboardCard{background:#111B25;border:1px solid #263746;border-left:2px solid #2F88F5;border-radius:3px;}"
            "QWidget#dashboardRoot QTableWidget{background:#0B1118;border:1px solid #263746;border-radius:4px;}"
        );
        return;
    }
    dashboardRoot_->setStyleSheet(
        "QWidget#dashboardRoot QFrame#monitorPanel{border:2px solid #F25555;}"
        "QWidget#dashboardRoot QFrame#dashboardCard{border:1px solid #8D343C;border-left:3px solid #F25555;}"
        "QWidget#dashboardRoot QTableWidget{border:1px solid #8D343C;}"
    );
}

void MainWindow::loadConfiguredVideoPreviewFrames(const QStringList& sources) {
    stopVideoPreview();
    cameraFrames_.clear();
    cameraImageRects_.clear();
    cameraSourceSizes_.clear();
    for (int index = 0; index < sources.size(); ++index) {
        const QString& source = sources[index];
        cv::VideoCapture capture = openCapture(
            source,
            hikTransportCombo_ == nullptr ? "tcp" : hikTransportCombo_->currentData().toString()
        );
        if (!capture.isOpened()) {
            appendLog(QString("[%1] 视频首帧读取失败。").arg(QString("camera_%1").arg(index + 1)));
            continue;
        }
        cv::Mat frame;
        if (!capture.read(frame) || frame.empty()) {
            appendLog(QString("[%1] 视频首帧为空。").arg(QString("camera_%1").arg(index + 1)));
            continue;
        }
        cameraFrames_.insert(QString("camera_%1").arg(index + 1), matToImage(frame));
    }
    composeMultiCameraPreview();
    appendLog(QString("已载入 %1 路本地视频首帧，可绘制 ROI。").arg(cameraFrames_.size()));
}

void MainWindow::loadVideoPreviewFrame() {
    const QString source = privatePath(sourceEdit_);
    if (source.isEmpty() || (!canBeRuntimeSource(source) && !QFileInfo::exists(source))) {
        return;
    }
    cv::VideoCapture cap = openCapture(
        source,
        hikTransportCombo_ == nullptr ? "tcp" : hikTransportCombo_->currentData().toString()
    );
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
