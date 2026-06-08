#pragma once

#include <QImage>
#include <QLabel>
#include <QMainWindow>
#include <QObject>
#include <QPoint>
#include <QRect>
#include <QString>
#include <QStringList>
#include <QThread>
#include <QVector>

#include <atomic>

class QComboBox;
class QDoubleSpinBox;
class QKeyEvent;
class QLineEdit;
class QMouseEvent;
class QPaintEvent;
class QPlainTextEdit;
class QPushButton;
class QSpinBox;
class QWidget;

class RoiPreviewLabel : public QLabel {
    Q_OBJECT

public:
    enum class DrawMode {
        FlowRoi,
        DetectRoi
    };

    explicit RoiPreviewLabel(QWidget* parent = nullptr);

    void setImage(const QImage& image);
    void setDrawMode(DrawMode mode);
    void clearCurrentRoi();
    void undoCurrentPoint();
    void finishCurrentPolygon();
    void setFlowRoiFromText(const QString& text);
    void setDetectRoiFromText(const QString& text);
    QString flowRoiText() const;
    QString detectRoiText() const;

signals:
    void roiChanged(RoiPreviewLabel::DrawMode mode, const QString& text);

protected:
    void paintEvent(QPaintEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void keyPressEvent(QKeyEvent* event) override;

private:
    QRect imageRectInLabel() const;
    QPoint labelToImagePoint(const QPoint& point) const;
    QPoint imageToLabelPoint(const QPoint& point) const;
    QVector<QPoint>& activePolygon();
    const QVector<QPoint>& activePolygon() const;
    bool& activeRoiClosed();
    bool activeRoiClosed() const;
    QString polygonToText(const QVector<QPoint>& polygon, bool closed) const;
    QVector<QPoint> textToPolygon(const QString& text) const;
    void emitCurrentRoi();
    void drawPolygon(QPainter& painter, const QVector<QPoint>& polygon, bool closed, const QColor& color, const QString& label) const;

    QImage image_;
    QVector<QPoint> flowRoi_;
    QVector<QPoint> detectRoi_;
    bool flowRoiClosed_ = false;
    bool detectRoiClosed_ = false;
    DrawMode drawMode_ = DrawMode::FlowRoi;
    QPoint draftCursor_;
    bool hasDraftCursor_ = false;
};

struct DetectJobConfig {
    QString ptPath;
    QString sourcePath;
    QString outputDir;
    QString workerPath;
    QString trackerPath;
    QString flowRoiText;
    QString detectRoiText;
    QString jamSignalPath;
    QStringList labels;
    int classFilterId = -1;
    int inputSize = 960;
    double confidence = 0.25;
    double iou = 0.45;
    QString device = "0";
    int previewFps = 60;
    int jamSeconds = 5;
};

class DetectionWorker : public QObject {
    Q_OBJECT

public:
    explicit DetectionWorker(DetectJobConfig config);

public slots:
    void run();
    void stop();

signals:
    void frameReady(const QImage& image);
    void log(const QString& message);
    void done(const QString& summary);
    void failed(const QString& error);

private:
    DetectJobConfig config_;
    std::atomic_bool stopped_ = false;
};

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

private slots:
    void browsePt();
    void browseSource();
    void browseOutput();
    void startDetection();
    void stopDetection();
    void showFrame(const QImage& image);
    void appendLog(const QString& message);
    void refreshModelMetadata();
    void runEnvironmentDiagnose();
    void detectionFinished(const QString& summary);
    void detectionFailed(const QString& error);
    void cleanupWorker();
    void loadVideoPreviewFrame();
    void applyHikvisionStream();

private:
    QWidget* buildPathPanel();
    QWidget* buildParamPanel();
    QWidget* buildRoiPanel();
    QWidget* buildActionPanel();
    DetectJobConfig currentDetectConfig() const;
    QString buildHikvisionRtsp() const;
    void loadSettings();
    void saveSettings() const;
    void populateClassCombo(const QStringList& labels);
    void setRoiDrawMode(RoiPreviewLabel::DrawMode mode);

    QLineEdit* ptEdit_ = nullptr;
    QLineEdit* sourceEdit_ = nullptr;
    QLineEdit* outputEdit_ = nullptr;
    QLineEdit* hikIpEdit_ = nullptr;
    QLineEdit* hikUserEdit_ = nullptr;
    QLineEdit* hikPasswordEdit_ = nullptr;
    QLineEdit* flowRoiEdit_ = nullptr;
    QLineEdit* detectRoiEdit_ = nullptr;
    QComboBox* classCombo_ = nullptr;
    QComboBox* deviceCombo_ = nullptr;
    QSpinBox* inputSizeSpin_ = nullptr;
    QSpinBox* videoFpsSpin_ = nullptr;
    QSpinBox* hikChannelSpin_ = nullptr;
    QSpinBox* jamSecondsSpin_ = nullptr;
    QDoubleSpinBox* confidenceSpin_ = nullptr;
    QDoubleSpinBox* iouSpin_ = nullptr;
    QPushButton* drawFlowRoiButton_ = nullptr;
    QPushButton* drawDetectRoiButton_ = nullptr;
    QPushButton* startButton_ = nullptr;
    QPushButton* stopButton_ = nullptr;
    QPushButton* diagnoseButton_ = nullptr;
    RoiPreviewLabel* previewLabel_ = nullptr;
    QPlainTextEdit* logEdit_ = nullptr;

    QStringList loadedLabels_;
    QThread* workerThread_ = nullptr;
    DetectionWorker* worker_ = nullptr;
};
