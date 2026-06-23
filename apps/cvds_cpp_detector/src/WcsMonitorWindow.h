#pragma once

#include "CameraTileWidget.h"
#include "CameraWorker.h"
#include "WcsConfig.h"
#include "WcsInferenceManager.h"
#include "WcsTcpClient.h"

#include <QHash>
#include <QJsonObject>
#include <QMainWindow>
#include <QThread>

class QLabel;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QGridLayout;
class QTableWidget;
class QTimer;

class WcsMonitorWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit WcsMonitorWindow(QWidget* parent = nullptr);
    ~WcsMonitorWindow() override;

private slots:
    void browseConfig();
    void reloadConfig();
    void startPreview();
    void stopPreview();
    void startMonitoring();
    void stopMonitoring();
    void appendLog(const QString& message);
    void handleSnapshot(const CameraRuntimeSnapshot& snapshot);
    void handleDashboardPayload(const QString& cameraId, const QString& roiId, const QJsonObject& payload);
    void sendHeartbeat();

private:
    QWidget* buildControlPanel();
    QWidget* buildMonitorPanel();
    void loadConfig(const QString& path);
    void rebuildCameraGrid();
    void refreshCameraTable();
    void setSystemStatus(const QString& status);
    int cameraTableRow(const QString& cameraId) const;
    QString defaultConfigPath() const;
    QString outputRootPath() const;

    MultiCameraSystemConfig config_;
    QString configPath_;
    QHash<QString, CameraTileWidget*> tiles_;
    QHash<QString, CameraRuntimeSnapshot> snapshots_;
    QHash<QString, QHash<QString, QJsonObject>> dashboardPayloads_;
    QHash<QString, QThread*> previewThreads_;
    QHash<QString, CameraWorker*> previewWorkers_;

    WcsTcpClient* wcsClient_ = nullptr;
    WcsInferenceManager* inferenceManager_ = nullptr;
    QTimer* heartbeatTimer_ = nullptr;

    QLineEdit* configPathEdit_ = nullptr;
    QLabel* systemStatusLabel_ = nullptr;
    QLabel* wcsStatusLabel_ = nullptr;
    QTableWidget* cameraTable_ = nullptr;
    QGridLayout* cameraGrid_ = nullptr;
    QPlainTextEdit* logEdit_ = nullptr;
    QPushButton* previewButton_ = nullptr;
    QPushButton* stopPreviewButton_ = nullptr;
    QPushButton* startButton_ = nullptr;
    QPushButton* stopButton_ = nullptr;
};
