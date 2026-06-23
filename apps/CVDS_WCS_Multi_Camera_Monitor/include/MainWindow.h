#pragma once

#include "InferenceManager.h"
#include "WcsTcpClient.h"

#include <QCheckBox>
#include <QComboBox>
#include <QCoreApplication>
#include <QGridLayout>
#include <QHash>
#include <QHBoxLayout>
#include <QImage>
#include <QLabel>
#include <QLineEdit>
#include <QMainWindow>
#include <QPixmap>
#include <QPushButton>
#include <QSpinBox>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTextEdit>
#include <QTimer>

class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

private slots:
    void loadConfig();
    void browseModel();
    void startMonitoring();
    void stopMonitoring();
    void handleFrameReady(const QString& cameraId, const QImage& image);
    void handleSnapshot(const CameraRuntimeSnapshot& snapshot);
    void handleFlowUpdate(const WcsFlowUpdate& update);
    void handleJamOn(const WcsJamEvent& event);
    void handleJamOff(const WcsJamEvent& event);
    void handlePipelineLog(const QString& message);
    void sendHeartbeat();

private:
    void buildUi();
    void rebuildCameraGrid();
    void refreshCameraTable();
    void updateButtons();
    void appendLog(const QString& message);
    QString defaultConfigPath() const;
    QString defaultOutputRoot() const;
    QLabel* tileForCamera(const QString& cameraId);

    MultiCameraSystemConfig config_;
    QString configPath_;
    QString outputRoot_;
    QWidget* central_ = nullptr;
    QLineEdit* configEdit_ = nullptr;
    QLineEdit* modelEdit_ = nullptr;
    QComboBox* deviceCombo_ = nullptr;
    QSpinBox* inputSizeSpin_ = nullptr;
    QCheckBox* wcsEnabledCheck_ = nullptr;
    QPushButton* loadButton_ = nullptr;
    QPushButton* modelButton_ = nullptr;
    QPushButton* startButton_ = nullptr;
    QPushButton* stopButton_ = nullptr;
    QGridLayout* grid_ = nullptr;
    QTableWidget* cameraTable_ = nullptr;
    QTextEdit* logEdit_ = nullptr;
    QHash<QString, QLabel*> tiles_;
    QHash<QString, CameraRuntimeSnapshot> snapshots_;
    QHash<QString, int> rowByCamera_;
    InferenceManager* inference_ = nullptr;
    WcsTcpClient* wcsClient_ = nullptr;
    QTimer heartbeatTimer_;
};
