#include "WcsMonitorWindow.h"

#include "RuntimePaths.h"

#include <QApplication>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QFormLayout>
#include <QGridLayout>
#include <QGroupBox>
#include <QHeaderView>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QScrollArea>
#include <QSplitter>
#include <QTableWidget>
#include <QTableWidgetItem>
#include <QTimer>
#include <QVBoxLayout>

#include <algorithm>
#include <cmath>

namespace {

QString statusText(const CameraRuntimeSnapshot& snapshot) {
    if (!snapshot.error.trimmed().isEmpty()) {
        return snapshot.status + " · " + snapshot.error;
    }
    return snapshot.status;
}

}  // namespace

WcsMonitorWindow::WcsMonitorWindow(QWidget* parent)
    : QMainWindow(parent),
      wcsClient_(new WcsTcpClient(this)),
      inferenceManager_(new WcsInferenceManager(this)),
      heartbeatTimer_(new QTimer(this)) {
    qRegisterMetaType<CameraRuntimeSnapshot>("CameraRuntimeSnapshot");
    setWindowTitle("CVDS WCS 多路视觉流量监测 " + RuntimePaths::versionText());
    resize(1280, 720);
    setMinimumSize(1024, 640);

    auto* splitter = new QSplitter(Qt::Horizontal, this);
    splitter->setChildrenCollapsible(false);
    splitter->addWidget(buildControlPanel());
    splitter->addWidget(buildMonitorPanel());
    splitter->setSizes({320, 960});
    setCentralWidget(splitter);

    heartbeatTimer_->setInterval(1000);
    connect(heartbeatTimer_, &QTimer::timeout, this, &WcsMonitorWindow::sendHeartbeat);

    connect(wcsClient_, &WcsTcpClient::stateChanged, this, [this](const QString& state) {
        wcsStatusLabel_->setText("WCS: " + state);
        appendLog("WCS 状态：" + state);
    });
    connect(wcsClient_, &WcsTcpClient::errorOccurred, this, [this](const QString& error) {
        appendLog("WCS 通信错误：" + error);
    });

    connect(inferenceManager_, &WcsInferenceManager::frameReady, this, [this](const QString& cameraId, const QImage& image) {
        if (tiles_.contains(cameraId)) {
            tiles_.value(cameraId)->setFrame(image);
        }
    });
    connect(inferenceManager_, &WcsInferenceManager::snapshotReady, this, &WcsMonitorWindow::handleSnapshot);
    connect(inferenceManager_, &WcsInferenceManager::dashboardPayloadReady, this, &WcsMonitorWindow::handleDashboardPayload);
    connect(inferenceManager_, &WcsInferenceManager::flowUpdateReady, wcsClient_, &WcsTcpClient::sendFlowUpdate);
    connect(inferenceManager_, &WcsInferenceManager::jamOnReady, wcsClient_, &WcsTcpClient::sendJamOn);
    connect(inferenceManager_, &WcsInferenceManager::jamOffReady, wcsClient_, &WcsTcpClient::sendJamOff);
    connect(inferenceManager_, &WcsInferenceManager::log, this, &WcsMonitorWindow::appendLog);
    connect(inferenceManager_, &WcsInferenceManager::failed, this, [this](const QString& cameraId, const QString& error) {
        appendLog(QString("[%1] %2").arg(cameraId, error));
        wcsClient_->sendErrorEvent(cameraId, "INFERENCE_ERROR", error);
    });
    connect(inferenceManager_, &WcsInferenceManager::allFinished, this, [this]() {
        stopButton_->setEnabled(false);
        startButton_->setEnabled(true);
        setSystemStatus("监测已停止");
    });

    setStyleSheet(
        "QWidget{background:#0B1118;color:#F3F7FA;font-family:'Microsoft YaHei UI';}"
        "QGroupBox{border:1px solid #263746;border-radius:5px;margin-top:12px;padding:8px;background:#111B25;color:#8FA5B8;font-weight:600;}"
        "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;background:#111B25;color:#8FA5B8;}"
        "QLineEdit,QPlainTextEdit,QTableWidget{background:#080D13;border:1px solid #263746;border-radius:4px;padding:6px;color:#F3F7FA;gridline-color:#263746;}"
        "QHeaderView::section{background:#172431;color:#8FA5B8;border:none;border-right:1px solid #263746;border-bottom:1px solid #263746;padding:6px;}"
        "QPushButton{background:#172431;border:1px solid #31485B;border-radius:4px;padding:7px;color:#DCE7EE;}"
        "QPushButton:hover{background:#21364A;border-color:#4DA3FF;}"
        "QPushButton#primaryButton{background:#2F88F5;border-color:#4DA3FF;color:white;font-weight:700;}"
        "QPushButton#dangerButton{background:#4A2024;border-color:#8D343C;color:#FFDDE0;font-weight:600;}"
        "QPushButton:disabled{background:#121B23;border-color:#26323D;color:#536574;}"
        "QLabel#statusPill{background:#10251F;border:1px solid #245B47;border-radius:3px;padding:4px 8px;color:#36C98F;font-weight:700;}"
    );

    loadConfig(defaultConfigPath());
    appendLog("WCS 多路监测窗口已启动。当前为 GPU worker 多进程调度版本。连接预览用于相机调试，开始监测后由检测 worker 接管视频源。支持按 camera_id + roi_id 聚合 dashboard payload。 ");
}

WcsMonitorWindow::~WcsMonitorWindow() {
    stopMonitoring();
    stopPreview();
}

QWidget* WcsMonitorWindow::buildControlPanel() {
    auto* panel = new QWidget(this);
    panel->setMinimumWidth(300);
    panel->setMaximumWidth(420);
    auto* layout = new QVBoxLayout(panel);
    layout->setContentsMargins(8, 8, 8, 8);
    layout->setSpacing(8);

    auto* title = new QLabel("WCS 多路视觉监测", panel);
    title->setStyleSheet("font-size:18px;font-weight:800;color:#F3F7FA;background:transparent;");
    layout->addWidget(title);

    systemStatusLabel_ = new QLabel("系统待机", panel);
    systemStatusLabel_->setObjectName("statusPill");
    wcsStatusLabel_ = new QLabel("WCS: 未连接", panel);
    wcsStatusLabel_->setObjectName("statusPill");
    layout->addWidget(systemStatusLabel_);
    layout->addWidget(wcsStatusLabel_);

    auto* configBox = new QGroupBox("配置", panel);
    auto* configLayout = new QFormLayout(configBox);
    configPathEdit_ = new QLineEdit(configBox);
    configPathEdit_->setReadOnly(true);
    auto* browseButton = new QPushButton("选择 cameras.wcs.json", configBox);
    auto* reloadButton = new QPushButton("重新加载配置", configBox);
    connect(browseButton, &QPushButton::clicked, this, &WcsMonitorWindow::browseConfig);
    connect(reloadButton, &QPushButton::clicked, this, &WcsMonitorWindow::reloadConfig);
    configLayout->addRow("配置文件", configPathEdit_);
    configLayout->addRow(QString(), browseButton);
    configLayout->addRow(QString(), reloadButton);
    layout->addWidget(configBox);

    auto* actionBox = new QGroupBox("运行控制", panel);
    auto* actionLayout = new QVBoxLayout(actionBox);
    previewButton_ = new QPushButton("连接多路预览", actionBox);
    stopPreviewButton_ = new QPushButton("停止预览", actionBox);
    startButton_ = new QPushButton("开始 WCS 监测", actionBox);
    stopButton_ = new QPushButton("停止 WCS 监测", actionBox);
    startButton_->setObjectName("primaryButton");
    stopButton_->setObjectName("dangerButton");
    stopPreviewButton_->setEnabled(false);
    stopButton_->setEnabled(false);
    connect(previewButton_, &QPushButton::clicked, this, &WcsMonitorWindow::startPreview);
    connect(stopPreviewButton_, &QPushButton::clicked, this, &WcsMonitorWindow::stopPreview);
    connect(startButton_, &QPushButton::clicked, this, &WcsMonitorWindow::startMonitoring);
    connect(stopButton_, &QPushButton::clicked, this, &WcsMonitorWindow::stopMonitoring);
    actionLayout->addWidget(previewButton_);
    actionLayout->addWidget(stopPreviewButton_);
    actionLayout->addWidget(startButton_);
    actionLayout->addWidget(stopButton_);
    layout->addWidget(actionBox);

    cameraTable_ = new QTableWidget(panel);
    cameraTable_->setColumnCount(7);
    cameraTable_->setHorizontalHeaderLabels({"相机", "线路", "皮带", "状态", "FPS", "计数", "堵包"});
    cameraTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    cameraTable_->verticalHeader()->setVisible(false);
    cameraTable_->setSelectionBehavior(QAbstractItemView::SelectRows);
    cameraTable_->setEditTriggers(QAbstractItemView::NoEditTriggers);
    layout->addWidget(cameraTable_, 1);

    logEdit_ = new QPlainTextEdit(panel);
    logEdit_->setReadOnly(true);
    logEdit_->setMaximumBlockCount(800);
    logEdit_->setMinimumHeight(150);
    layout->addWidget(logEdit_);
    return panel;
}

QWidget* WcsMonitorWindow::buildMonitorPanel() {
    auto* shell = new QWidget(this);
    auto* shellLayout = new QVBoxLayout(shell);
    shellLayout->setContentsMargins(8, 8, 8, 8);
    shellLayout->setSpacing(8);

    auto* hint = new QLabel("多路相机画面 · 每个 Tile 显示在线状态、FPS、累计流量、区域内数量和堵包状态。堵包时 Tile 红色高亮。", shell);
    hint->setStyleSheet("background:transparent;color:#8FA5B8;");
    shellLayout->addWidget(hint);

    auto* scroll = new QScrollArea(shell);
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    auto* gridHost = new QWidget(scroll);
    cameraGrid_ = new QGridLayout(gridHost);
    cameraGrid_->setContentsMargins(0, 0, 0, 0);
    cameraGrid_->setSpacing(8);
    scroll->setWidget(gridHost);
    shellLayout->addWidget(scroll, 1);
    return shell;
}

void WcsMonitorWindow::browseConfig() {
    const QString path = QFileDialog::getOpenFileName(
        this,
        "选择 WCS 多摄像头配置",
        QFileInfo(configPath_).absolutePath(),
        "WCS Config (*.json);;All Files (*)"
    );
    if (!path.isEmpty()) {
        loadConfig(path);
    }
}

void WcsMonitorWindow::reloadConfig() {
    if (!configPath_.isEmpty()) {
        loadConfig(configPath_);
    }
}

void WcsMonitorWindow::loadConfig(const QString& path) {
    try {
        config_ = loadMultiCameraSystemConfig(path);
        configPath_ = path;
        configPathEdit_->setText(path);
        wcsClient_->configure(config_.wcs);
        rebuildCameraGrid();
        refreshCameraTable();
        setSystemStatus(QString("已加载 %1 路相机").arg(config_.cameras.size()));
        appendLog("已加载 WCS 配置：" + path);
    } catch (const std::exception& ex) {
        QMessageBox::warning(this, "配置加载失败", QString::fromUtf8(ex.what()));
        appendLog("配置加载失败：" + QString::fromUtf8(ex.what()));
    }
}

void WcsMonitorWindow::rebuildCameraGrid() {
    while (QLayoutItem* item = cameraGrid_->takeAt(0)) {
        if (item->widget() != nullptr) {
            item->widget()->deleteLater();
        }
        delete item;
    }
    tiles_.clear();

    const int enabledCount = std::max(1, std::count_if(config_.cameras.cbegin(), config_.cameras.cend(), [](const CameraConfig& camera) {
        return camera.enabled;
    }));
    const int columns = enabledCount <= 4 ? 2 : (enabledCount <= 9 ? 3 : 4);
    int tileIndex = 0;
    for (const CameraConfig& camera : config_.cameras) {
        if (!camera.enabled) {
            continue;
        }
        auto* tile = new CameraTileWidget();
        tile->setCameraConfig(camera);
        tiles_.insert(camera.cameraId, tile);
        cameraGrid_->addWidget(tile, tileIndex / columns, tileIndex % columns);
        ++tileIndex;
    }
}

void WcsMonitorWindow::startPreview() {
    if (!previewWorkers_.isEmpty()) {
        return;
    }
    stopMonitoring();
    for (const CameraConfig& camera : config_.cameras) {
        if (!camera.enabled) {
            continue;
        }
        auto* thread = new QThread(this);
        auto* worker = new CameraWorker(camera);
        worker->moveToThread(thread);
        previewThreads_.insert(camera.cameraId, thread);
        previewWorkers_.insert(camera.cameraId, worker);
        connect(thread, &QThread::started, worker, &CameraWorker::run);
        connect(worker, &CameraWorker::frameReady, this, [this](const QString& cameraId, const QImage& image) {
            if (tiles_.contains(cameraId)) {
                tiles_.value(cameraId)->setFrame(image);
            }
        });
        connect(worker, &CameraWorker::snapshotReady, this, &WcsMonitorWindow::handleSnapshot);
        connect(worker, &CameraWorker::log, this, &WcsMonitorWindow::appendLog);
        connect(worker, &CameraWorker::failed, this, [this](const QString& cameraId, const QString& error) {
            appendLog(QString("[%1] %2").arg(cameraId, error));
        });
        connect(worker, &CameraWorker::finished, this, [this, worker, thread](const QString& cameraId) {
            previewWorkers_.remove(cameraId);
            previewThreads_.remove(cameraId);
            thread->quit();
            worker->deleteLater();
            thread->deleteLater();
        });
        thread->start();
    }
    previewButton_->setEnabled(false);
    stopPreviewButton_->setEnabled(true);
    setSystemStatus("多路预览运行中");
}

void WcsMonitorWindow::stopPreview() {
    const QList<CameraWorker*> workers = previewWorkers_.values();
    for (CameraWorker* worker : workers) {
        QMetaObject::invokeMethod(worker, "stop", Qt::QueuedConnection);
    }
    const QList<QThread*> threads = previewThreads_.values();
    for (QThread* thread : threads) {
        thread->quit();
        thread->wait(3000);
    }
    previewWorkers_.clear();
    previewThreads_.clear();
    previewButton_->setEnabled(true);
    stopPreviewButton_->setEnabled(false);
    if (!inferenceManager_->isRunning()) {
        setSystemStatus("预览已停止");
    }
}

void WcsMonitorWindow::startMonitoring() {
    stopPreview();
    wcsClient_->configure(config_.wcs);
    if (config_.wcs.enabled) {
        wcsClient_->start();
        heartbeatTimer_->start(config_.wcs.heartbeatMs);
    }

    WcsInferenceRuntimeConfig runtime;
    runtime.workerPath = RuntimePaths::workerExePath();
    runtime.outputRoot = outputRootPath();
    runtime.previewFps = 15;
    runtime.classFilterId = -1;
    inferenceManager_->configure(config_, runtime);
    inferenceManager_->start();
    startButton_->setEnabled(false);
    stopButton_->setEnabled(true);
    previewButton_->setEnabled(false);
    setSystemStatus("WCS 监测运行中");
}

void WcsMonitorWindow::stopMonitoring() {
    heartbeatTimer_->stop();
    inferenceManager_->stop();
    wcsClient_->stop();
    startButton_->setEnabled(true);
    stopButton_->setEnabled(false);
    previewButton_->setEnabled(true);
    setSystemStatus("WCS 监测已停止");
}

void WcsMonitorWindow::appendLog(const QString& message) {
    if (logEdit_ == nullptr) {
        return;
    }
    logEdit_->appendPlainText(QDateTime::currentDateTime().toString("HH:mm:ss.zzz ") + message);
}

void WcsMonitorWindow::handleSnapshot(const CameraRuntimeSnapshot& snapshot) {
    snapshots_.insert(snapshot.cameraId, snapshot);
    if (tiles_.contains(snapshot.cameraId)) {
        tiles_.value(snapshot.cameraId)->setSnapshot(snapshot);
    }
    if (config_.wcs.enabled && wcsClient_->isConnected()) {
        wcsClient_->sendCameraStatus(snapshot);
    }
    refreshCameraTable();
}

void WcsMonitorWindow::handleDashboardPayload(const QString& cameraId, const QString& roiId, const QJsonObject& payload) {
    dashboardPayloads_[cameraId].insert(roiId, payload);
}

void WcsMonitorWindow::sendHeartbeat() {
    int online = 0;
    for (const CameraRuntimeSnapshot& snapshot : snapshots_) {
        const QString status = snapshot.status.toUpper();
        if (status == "ONLINE" || status == "RUNNING" || status == "JAM") {
            ++online;
        }
    }
    wcsClient_->sendHeartbeat(online, config_.cameras.size(), 0.0);
}

void WcsMonitorWindow::refreshCameraTable() {
    if (cameraTable_ == nullptr) {
        return;
    }
    cameraTable_->setRowCount(config_.cameras.size());
    for (int row = 0; row < config_.cameras.size(); ++row) {
        const CameraConfig& camera = config_.cameras[row];
        const CameraRuntimeSnapshot snapshot = snapshots_.value(camera.cameraId);
        const QStringList values = {
            camera.cameraId,
            camera.lineId,
            camera.beltId,
            statusText(snapshot),
            QString::number(std::max(snapshot.decodeFps, snapshot.inferFps), 'f', 1),
            QString::number(snapshot.totalCount),
            snapshot.jamActive ? "是" : "否",
        };
        for (int column = 0; column < values.size(); ++column) {
            auto* item = cameraTable_->item(row, column);
            if (item == nullptr) {
                item = new QTableWidgetItem();
                cameraTable_->setItem(row, column, item);
            }
            item->setText(values[column]);
        }
    }
}

void WcsMonitorWindow::setSystemStatus(const QString& status) {
    if (systemStatusLabel_ != nullptr) {
        systemStatusLabel_->setText(status);
    }
}

int WcsMonitorWindow::cameraTableRow(const QString& cameraId) const {
    for (int row = 0; row < config_.cameras.size(); ++row) {
        if (config_.cameras[row].cameraId == cameraId) {
            return row;
        }
    }
    return -1;
}

QString WcsMonitorWindow::defaultConfigPath() const {
    const QString preferred = QDir(RuntimePaths::configDir()).filePath("cameras.wcs.json");
    if (QFileInfo::exists(preferred)) {
        return preferred;
    }
    return QDir(RuntimePaths::configDir()).filePath("cameras.wcs.example.json");
}

QString WcsMonitorWindow::outputRootPath() const {
    const QString stamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
    return QDir(RuntimePaths::defaultOutputDir()).filePath("wcs_multi_camera_" + stamp);
}
