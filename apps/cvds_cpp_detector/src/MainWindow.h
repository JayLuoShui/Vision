#pragma once

#include "RegionConfig.h"

#include <QByteArray>
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
class QCheckBox;
class QDoubleSpinBox;
class QKeyEvent;
class QLineEdit;
class QMouseEvent;
class QPaintEvent;
class QPlainTextEdit;
class QProcess;
class QPushButton;
class QSpinBox;
class QTableWidget;
class QTimer;
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
    void setFlowRegions(const QVector<RegionConfig>& regions);
    void setActiveRegionId(const QString& regionId);
    void setJamRegionIds(const QStringList& regionIds);
    void setAlertFlashVisible(bool visible);
    void setRoiEditingEnabled(bool enabled);
    void clearCurrentRoi();
    void undoCurrentPoint();
    void finishCurrentPolygon();
    void setFlowRoiFromText(const QString& text);
    void setDetectRoiFromText(const QString& text);
    QString flowRoiText() const;
    QString detectRoiText() const;

signals:
    void flowRegionChanged(const QString& regionId, const QVector<QPoint>& polygon, bool closed);
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
    int activeRegionIndex() const;
    void syncActiveFlowRegion();
    QVector<QPoint>& activePolygon();
    const QVector<QPoint>& activePolygon() const;
    bool& activeRoiClosed();
    bool activeRoiClosed() const;
    QString polygonToText(const QVector<QPoint>& polygon, bool closed) const;
    QVector<QPoint> textToPolygon(const QString& text) const;
    void emitCurrentRoi();
    void drawPolygon(QPainter& painter, const QVector<QPoint>& polygon, bool closed, const QColor& color, const QString& label) const;

    QImage image_;
    QVector<RegionConfig> flowRegions_;
    QString activeRegionId_;
    QStringList jamRegionIds_;
    bool alertFlashVisible_ = false;
    bool roiEditingEnabled_ = true;
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
    QString regionsPath;
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
    void dashboardPayloadReady(const QByteArray& payload);
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
    void updateDashboard(const QByteArray& payload);
    void appendLog(const QString& message);
    void refreshModelMetadata();
    void runEnvironmentDiagnose();
    void detectionFinished(const QString& summary);
    void detectionFailed(const QString& error);
    void cleanupWorker();
    void loadVideoPreviewFrame();
    void applyHikvisionStream();
    void addRegion();
    void renameCurrentRegion();
    void deleteCurrentRegion();
    void saveRegionConfig();
    void loadRegionConfig();
    void toggleAlarmFlash();

private:
    QWidget* buildPathPanel();
    QWidget* buildParamPanel();
    QWidget* buildRoiPanel();
    QWidget* buildActionPanel();
    QWidget* buildDashboardPanel();
    DetectJobConfig currentDetectConfig() const;
    QString buildHikvisionRtsp() const;
    void loadSettings();
    void saveSettings() const;
    void populateClassCombo(const QStringList& labels);
    void beginModelMetadataRefresh(bool startDetectionAfterSuccess);
    void finishModelMetadataRefresh(QProcess* process, const QString& failure);
    void setRoiDrawMode(RoiPreviewLabel::DrawMode mode);
    void ensureDefaultRegion();
    void refreshRegionSelectors();
    void applyRegionSelection();
    void syncCurrentRegionEditors();
    void refreshRegionTable();
    void setDashboardAlarmActive(bool active);
    void updateAlertStyle();
    RegionConfigDocument buildRegionConfigDocument() const;
    int findRegionIndexById(const QString& regionId) const;
    QString nextRegionId() const;
    void restoreRegionConfigDocument(const RegionConfigDocument& document);
    QVector<QPoint> parseEditablePolygonText(const QString& text, const QString& label, bool allowEmpty) const;
    void updateDetectRoiFromEditor();
    void setConfigurationEditingEnabled(bool enabled);

    QLineEdit* ptEdit_ = nullptr;
    QLineEdit* sourceEdit_ = nullptr;
    QLineEdit* outputEdit_ = nullptr;
    QLineEdit* hikIpEdit_ = nullptr;
    QLineEdit* hikUserEdit_ = nullptr;
    QLineEdit* hikPasswordEdit_ = nullptr;
    QLineEdit* regionNameEdit_ = nullptr;
    QLineEdit* flowRoiEdit_ = nullptr;
    QLineEdit* detectRoiEdit_ = nullptr;
    QComboBox* regionCombo_ = nullptr;
    QComboBox* totalCountRegionCombo_ = nullptr;
    QComboBox* classCombo_ = nullptr;
    QComboBox* deviceCombo_ = nullptr;
    QCheckBox* countEnabledCheck_ = nullptr;
    QCheckBox* jamEnabledCheck_ = nullptr;
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
    QLabel* kpiTotalCountValueLabel_ = nullptr;
    QLabel* kpiStatusValueLabel_ = nullptr;
    QLabel* kpiInsideCountValueLabel_ = nullptr;
    QLabel* kpiJamCountValueLabel_ = nullptr;
    QTableWidget* regionTable_ = nullptr;
    QPlainTextEdit* logEdit_ = nullptr;
    QTimer* flashTimer_ = nullptr;
    QWidget* dashboardRoot_ = nullptr;
    QWidget* pathPanel_ = nullptr;
    QWidget* paramPanel_ = nullptr;
    QWidget* roiPanel_ = nullptr;

    QStringList loadedLabels_;
    QString loadedModelPath_;
    QString modelInspectPath_;
    QProcess* modelInspectProcess_ = nullptr;
    bool startDetectionAfterModelInspect_ = false;
    bool modelInspectTimedOut_ = false;
    QVector<RegionConfig> regions_;
    QVector<RegionRuntimeState> regionRuntimeStates_;
    QString totalCountRegionId_;
    QString currentRegionId_;
    int dashboardTotalCount_ = 0;
    int dashboardInsideCount_ = 0;
    int dashboardJamCount_ = 0;
    bool dashboardJamActive_ = false;
    bool dashboardFlashVisible_ = false;
    QString dashboardStatusText_ = "待机";
    QThread* workerThread_ = nullptr;
    DetectionWorker* worker_ = nullptr;
};
