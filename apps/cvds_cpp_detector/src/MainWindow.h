#pragma once

#include "RegionConfig.h"
#include "pipeline/VideoPipeline.h"

#include <QByteArray>
#include <QHash>
#include <QImage>
#include <QLabel>
#include <QMainWindow>
#include <QObject>
#include <QPoint>
#include <QRect>
#include <QSize>
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
class QPushButton;
class QResizeEvent;
class QSpinBox;
class QSplitter;
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
    void imageClicked(const QPoint& imagePoint);

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

class VideoPreviewWorker : public QObject {
    Q_OBJECT

public:
    VideoPreviewWorker(QString source, QString rtspTransport);

public slots:
    void run();
    void stop();

signals:
    void frameReady(const QImage& image);
    void failed(const QString& error);
    void finished();

private:
    QString source_;
    QString rtspTransport_;
    std::atomic_bool stopped_ = false;
};

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

protected:
    void resizeEvent(QResizeEvent* event) override;

private slots:
    void browseModel();
    void browseOpenVinoDirectory();
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
    void applyLocalVideoSources();
    void applyHikvisionStream();
    void testVideoStream();
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
    QWidget* buildControlPanel();
    QWidget* buildDashboardPanel();
    QPushButton* buildSidebarNavigationButton(const QString& text, QWidget* panel, QWidget* parent);
    void setSidebarPanelVisible(QWidget* panel, QPushButton* button);
    void resizeSidebarToStitchRatio();
    void setSettingsPanelCollapsed(bool collapsed);
    void startVideoPreview();
    void launchPendingVideoPreview();
    void stopVideoPreview();
    void cleanupPreview(QThread* thread);
    void refreshRuntimeOverview();
    VideoPipeline::Config currentDetectConfig() const;
    QStringList configuredSourcePaths() const;
    QVector<int> configuredHikvisionChannels() const;
    bool startConfiguredPipelines(const QStringList& sources);
    void cleanupPipeline(QThread* thread);
    void composeMultiCameraPreview();
    void loadConfiguredVideoPreviewFrames(const QStringList& sources);
    QString buildHikvisionRtsp() const;
    QString buildHikvisionRtsp(int channel) const;
    void loadSettings();
    void saveSettings() const;
    void populateClassCombo(const QStringList& labels);
    void refreshDeviceOptions(const QString& preferredDevice = {});
    void setRoiDrawMode(RoiPreviewLabel::DrawMode mode);
    void ensureDefaultRegion();
    void refreshRegionSelectors();
    void applyRegionSelection();
    void syncCurrentRegionEditors();
    void refreshRegionTable();
    void setDashboardAlarmActive(bool active);
    void updateAlertStyle();
    RegionConfigDocument buildRegionConfigDocument() const;
    RegionConfigDocument regionDocumentForCamera(const QString& cameraId, bool multiCamera) const;
    int findRegionIndexById(const QString& regionId) const;
    QString nextRegionId() const;
    void restoreRegionConfigDocument(const RegionConfigDocument& document);
    QVector<QPoint> parseEditablePolygonText(const QString& text, const QString& label, bool allowEmpty) const;
    void updateDetectRoiFromEditor();
    void updateDashboardForCamera(const QString& cameraId, const QByteArray& payload);
    void aggregateDashboardFromCameraStates();
    void selectCameraAtPoint(const QPoint& imagePoint);
    void selectDrawingRegionForCamera(const QString& cameraId);
    bool isDetectionRunning() const;
    void setConfigurationEditingEnabled(bool enabled);

    QPlainTextEdit* modelEdit_ = nullptr;
    QLineEdit* sourceEdit_ = nullptr;
    QLineEdit* outputEdit_ = nullptr;
    QPlainTextEdit* multiSourceEdit_ = nullptr;
    QLineEdit* hikIpEdit_ = nullptr;
    QLineEdit* hikUserEdit_ = nullptr;
    QLineEdit* hikPasswordEdit_ = nullptr;
    QLineEdit* multiHikChannelEdit_ = nullptr;
    QLineEdit* regionNameEdit_ = nullptr;
    QLineEdit* flowRoiEdit_ = nullptr;
    QLineEdit* detectRoiEdit_ = nullptr;
    QComboBox* regionCombo_ = nullptr;
    QComboBox* totalCountRegionCombo_ = nullptr;
    QComboBox* classCombo_ = nullptr;
    QComboBox* backendCombo_ = nullptr;
    QComboBox* deviceCombo_ = nullptr;
    QComboBox* sourceModeCombo_ = nullptr;
    QComboBox* hikStreamCombo_ = nullptr;
    QComboBox* hikTransportCombo_ = nullptr;
    QCheckBox* countEnabledCheck_ = nullptr;
    QCheckBox* jamEnabledCheck_ = nullptr;
    QSpinBox* inputSizeSpin_ = nullptr;
    QSpinBox* videoFpsSpin_ = nullptr;
    QSpinBox* hikChannelSpin_ = nullptr;
    QLineEdit* hikRtspPortEdit_ = nullptr;
    QSpinBox* jamSecondsSpin_ = nullptr;
    QDoubleSpinBox* confidenceSpin_ = nullptr;
    QDoubleSpinBox* iouSpin_ = nullptr;
    QPushButton* drawFlowRoiButton_ = nullptr;
    QPushButton* drawDetectRoiButton_ = nullptr;
    QPushButton* startButton_ = nullptr;
    QPushButton* stopButton_ = nullptr;
    QPushButton* diagnoseButton_ = nullptr;
    QPushButton* settingsToggleButton_ = nullptr;
    QPushButton* regionDetailsToggleButton_ = nullptr;
    QPushButton* logToggleButton_ = nullptr;
    RoiPreviewLabel* previewLabel_ = nullptr;
    QLabel* kpiTotalCountValueLabel_ = nullptr;
    QLabel* kpiStatusValueLabel_ = nullptr;
    QLabel* kpiInsideCountValueLabel_ = nullptr;
    QLabel* kpiJamCountValueLabel_ = nullptr;
    QLabel* systemStatusLabel_ = nullptr;
    QLabel* sourceStatusLabel_ = nullptr;
    QLabel* channelStatusLabel_ = nullptr;
    QLabel* clockLabel_ = nullptr;
    QLabel* regionEmptyLabel_ = nullptr;
    QTableWidget* regionTable_ = nullptr;
    QPlainTextEdit* logEdit_ = nullptr;
    QTimer* flashTimer_ = nullptr;
    QTimer* clockTimer_ = nullptr;
    QWidget* dashboardRoot_ = nullptr;
    QWidget* regionDetailsContent_ = nullptr;
    QSplitter* mainSplitter_ = nullptr;
    QWidget* settingsPanel_ = nullptr;
    QWidget* pathPanel_ = nullptr;
    QWidget* paramPanel_ = nullptr;
    QWidget* roiPanel_ = nullptr;
    QWidget* controlPanel_ = nullptr;
    QWidget* actionPanel_ = nullptr;
    QWidget* streamSettingsWidget_ = nullptr;
    QVector<QPushButton*> sidebarButtons_;

    QStringList loadedLabels_;
    QString loadedModelPath_;
    QVector<RegionConfig> regions_;
    QVector<RegionRuntimeState> regionRuntimeStates_;
    QVector<RegionRuntimeState> dashboardRuntimeStates_;
    QString totalCountRegionId_;
    QString currentRegionId_;
    int dashboardTotalCount_ = 0;
    int dashboardInsideCount_ = 0;
    int dashboardJamCount_ = 0;
    bool dashboardJamActive_ = false;
    bool dashboardFlashVisible_ = false;
    bool settingsPanelCollapsed_ = false;
    bool previewFrameAccepted_ = false;
    bool previewComposePending_ = false;
    bool startDetectionAfterPreviewStops_ = false;
    QString dashboardStatusText_ = "待机";
    QStringList pendingPreviewSources_;
    QString pendingPreviewTransport_;
    QThread* previewThread_ = nullptr;
    VideoPreviewWorker* previewWorker_ = nullptr;
    QThread* pipelineThread_ = nullptr;
    VideoPipeline* pipeline_ = nullptr;
    struct PipelineRuntime {
        QString cameraId;
        QThread* thread = nullptr;
        VideoPipeline* pipeline = nullptr;
    };
    struct PreviewRuntime {
        QString cameraId;
        QThread* thread = nullptr;
        VideoPreviewWorker* worker = nullptr;
    };
    QVector<PreviewRuntime> previewRuntimes_;
    QVector<PipelineRuntime> pipelineRuntimes_;
    QHash<QString, QImage> cameraFrames_;
    QHash<QString, QRect> cameraImageRects_;
    QHash<QString, QSize> cameraSourceSizes_;
    QHash<QString, QVector<RegionRuntimeState>> cameraRegionRuntimeStates_;
};
