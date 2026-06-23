#pragma once

#include "WcsConfig.h"

#include <QFrame>
#include <QImage>

class QLabel;

class CameraTileWidget : public QFrame {
    Q_OBJECT

public:
    explicit CameraTileWidget(QWidget* parent = nullptr);

    void setCameraConfig(const CameraConfig& config);
    QString cameraId() const;
    void setFrame(const QImage& image);
    void setSnapshot(const CameraRuntimeSnapshot& snapshot);
    void setSelected(bool selected);

protected:
    void resizeEvent(QResizeEvent* event) override;

private:
    void refreshFramePixmap();
    void refreshStyle();

    CameraConfig config_;
    CameraRuntimeSnapshot snapshot_;
    QImage lastFrame_;
    QLabel* titleLabel_ = nullptr;
    QLabel* statusLabel_ = nullptr;
    QLabel* frameLabel_ = nullptr;
    QLabel* metricsLabel_ = nullptr;
    bool selected_ = false;
};
