#include "CameraTileWidget.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QPixmap>
#include <QResizeEvent>
#include <QSizePolicy>
#include <QVBoxLayout>

CameraTileWidget::CameraTileWidget(QWidget* parent)
    : QFrame(parent) {
    setObjectName("cameraTile");
    setFrameShape(QFrame::NoFrame);
    setMinimumSize(240, 160);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);

    auto* root = new QVBoxLayout(this);
    root->setContentsMargins(6, 6, 6, 6);
    root->setSpacing(5);

    auto* header = new QHBoxLayout();
    header->setContentsMargins(0, 0, 0, 0);
    header->setSpacing(6);
    titleLabel_ = new QLabel("未配置相机", this);
    titleLabel_->setObjectName("cameraTileTitle");
    statusLabel_ = new QLabel("OFFLINE", this);
    statusLabel_->setObjectName("cameraTileStatus");
    statusLabel_->setAlignment(Qt::AlignCenter);
    header->addWidget(titleLabel_, 1);
    header->addWidget(statusLabel_);
    root->addLayout(header);

    frameLabel_ = new QLabel("等待视频流", this);
    frameLabel_->setObjectName("cameraTileFrame");
    frameLabel_->setAlignment(Qt::AlignCenter);
    frameLabel_->setMinimumSize(200, 112);
    frameLabel_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    root->addWidget(frameLabel_, 1);

    metricsLabel_ = new QLabel("FPS -- | Count 0 | Inside 0 | Jam 0", this);
    metricsLabel_->setObjectName("cameraTileMetrics");
    root->addWidget(metricsLabel_);
    refreshStyle();
}

void CameraTileWidget::setCameraConfig(const CameraConfig& config) {
    config_ = config;
    snapshot_.cameraId = config.cameraId;
    snapshot_.lineId = config.lineId;
    snapshot_.beltId = config.beltId;
    const QString title = QString("%1  %2 / %3").arg(config.cameraId, config.lineId, config.beltId);
    titleLabel_->setText(config.name.trimmed().isEmpty() ? title : config.name + " · " + title);
    statusLabel_->setText(config.enabled ? "READY" : "DISABLED");
    refreshStyle();
}

QString CameraTileWidget::cameraId() const {
    return config_.cameraId;
}

void CameraTileWidget::setFrame(const QImage& image) {
    lastFrame_ = image;
    refreshFramePixmap();
}

void CameraTileWidget::setSnapshot(const CameraRuntimeSnapshot& snapshot) {
    snapshot_ = snapshot;
    statusLabel_->setText(snapshot.status);
    metricsLabel_->setText(
        QString("Decode %1 FPS | Infer %2 FPS | Count %3 | Inside %4 | Jam %5")
            .arg(snapshot.decodeFps, 0, 'f', 1)
            .arg(snapshot.inferFps, 0, 'f', 1)
            .arg(snapshot.totalCount)
            .arg(snapshot.insideCount)
            .arg(snapshot.jamCount)
    );
    if (!snapshot.error.trimmed().isEmpty()) {
        frameLabel_->setToolTip(snapshot.error);
    } else {
        frameLabel_->setToolTip({});
    }
    refreshStyle();
}

void CameraTileWidget::setSelected(bool selected) {
    selected_ = selected;
    refreshStyle();
}

void CameraTileWidget::resizeEvent(QResizeEvent* event) {
    QFrame::resizeEvent(event);
    refreshFramePixmap();
}

void CameraTileWidget::refreshFramePixmap() {
    if (lastFrame_.isNull()) {
        frameLabel_->setText("等待视频流");
        frameLabel_->setPixmap({});
        return;
    }
    frameLabel_->setText({});
    frameLabel_->setPixmap(QPixmap::fromImage(lastFrame_).scaled(
        frameLabel_->size(),
        Qt::KeepAspectRatio,
        Qt::SmoothTransformation
    ));
}

void CameraTileWidget::refreshStyle() {
    const bool jam = snapshot_.jamActive || snapshot_.status.compare("JAM", Qt::CaseInsensitive) == 0;
    const bool online = snapshot_.status.compare("ONLINE", Qt::CaseInsensitive) == 0
        || snapshot_.status.compare("RUNNING", Qt::CaseInsensitive) == 0;
    const QString border = jam ? "#F25555" : (selected_ ? "#4DA3FF" : "#263746");
    const QString statusBg = jam ? "#4A2024" : (online ? "#10251F" : "#172431");
    const QString statusFg = jam ? "#FFDDE0" : (online ? "#36C98F" : "#B8C8D4");
    setStyleSheet(QString(
        "QFrame#cameraTile{background:#080D13;border:2px solid %1;border-radius:5px;}"
        "QLabel#cameraTileTitle{background:transparent;color:#F3F7FA;font-weight:700;}"
        "QLabel#cameraTileStatus{background:%2;color:%3;border:1px solid %1;border-radius:3px;padding:2px 6px;font-weight:700;}"
        "QLabel#cameraTileFrame{background:#05080D;color:#708395;border:1px solid #182431;}"
        "QLabel#cameraTileMetrics{background:transparent;color:#B8C8D4;font-size:10px;}"
    ).arg(border, statusBg, statusFg));
}
