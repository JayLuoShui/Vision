#include "MainWindow.h"

#include <QComboBox>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
#include <QFormLayout>
#include <QGridLayout>
#include <QHeaderView>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QTableWidget>
#include <QTextEdit>
#include <QVBoxLayout>

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    qRegisterMetaType<CameraRuntimeSnapshot>();
    inference_ = new InferenceManager(this);
    wcsClient_ = new WcsTcpClient(this);
    buildUi();
    configPath_ = defaultConfigPath();
    configEdit_->setText(configPath_);
    loadConfig();
    connect(&heartbeatTimer_, &QTimer::timeout, this, &MainWindow::sendHeartbeat);
}

MainWindow::~MainWindow() { stopMonitoring(); }

void MainWindow::buildUi() {
    central_ = new QWidget(this);
    setCentralWidget(central_);
    auto* root = new QVBoxLayout(central_);
    auto* form = new QFormLayout();
    configEdit_ = new QLineEdit(this);
    modelEdit_ = new QLineEdit(this);
    deviceCombo_ = new QComboBox(this);
    deviceCombo_->addItems({"AUTO", "CPU", "GPU", "NPU"});
    inputSizeSpin_ = new QSpinBox(this);
    inputSizeSpin_->setRange(320, 2048);
    inputSizeSpin_->setValue(640);
    wcsEnabledCheck_ = new QCheckBox("启用 WCS TCP 上报", this);
    loadButton_ = new QPushButton("加载配置", this);
    modelButton_ = new QPushButton("选择 OpenVINO XML/目录", this);
    startButton_ = new QPushButton("开始监测", this);
    stopButton_ = new QPushButton("停止", this);
    form->addRow("配置", configEdit_);
    form->addRow("OpenVINO 模型", modelEdit_);
    form->addRow("设备", deviceCombo_);
    form->addRow("输入尺寸", inputSizeSpin_);
    form->addRow("WCS", wcsEnabledCheck_);
    root->addLayout(form);
    auto* buttons = new QHBoxLayout();
    buttons->addWidget(loadButton_);
    buttons->addWidget(modelButton_);
    buttons->addWidget(startButton_);
    buttons->addWidget(stopButton_);
    root->addLayout(buttons);
    grid_ = new QGridLayout();
    root->addLayout(grid_, 3);
    cameraTable_ = new QTableWidget(this);
    cameraTable_->setColumnCount(8);
    cameraTable_->setHorizontalHeaderLabels({"Camera", "Line", "Belt", "Status", "Decode FPS", "Infer FPS", "Count", "Jam"});
    cameraTable_->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    root->addWidget(cameraTable_, 1);
    logEdit_ = new QTextEdit(this);
    logEdit_->setReadOnly(true);
    root->addWidget(logEdit_, 1);
    connect(loadButton_, &QPushButton::clicked, this, &MainWindow::loadConfig);
    connect(modelButton_, &QPushButton::clicked, this, &MainWindow::browseModel);
    connect(startButton_, &QPushButton::clicked, this, &MainWindow::startMonitoring);
    connect(stopButton_, &QPushButton::clicked, this, &MainWindow::stopMonitoring);
    connect(inference_, &InferenceManager::frameReady, this, &MainWindow::handleFrameReady);
    connect(inference_, &InferenceManager::snapshotReady, this, &MainWindow::handleSnapshot);
    connect(inference_, &InferenceManager::flowUpdateReady, this, &MainWindow::handleFlowUpdate);
    connect(inference_, &InferenceManager::jamOnReady, this, &MainWindow::handleJamOn);
    connect(inference_, &InferenceManager::jamOffReady, this, &MainWindow::handleJamOff);
    connect(inference_, &InferenceManager::log, this, &MainWindow::handlePipelineLog);
}

void MainWindow::loadConfig() {
    configPath_ = configEdit_->text().trimmed();
    config_ = loadMultiCameraSystemConfig(configPath_);
    if (!modelEdit_->text().trimmed().isEmpty()) config_.inference.modelPath = modelEdit_->text().trimmed();
    if (!config_.inference.modelPath.isEmpty()) modelEdit_->setText(config_.inference.modelPath);
    deviceCombo_->setCurrentText(config_.inference.device.toUpper().isEmpty() ? "AUTO" : config_.inference.device.toUpper());
    inputSizeSpin_->setValue(config_.inference.inputSize > 0 ? config_.inference.inputSize : 640);
    wcsEnabledCheck_->setChecked(config_.wcs.enabled);
    rebuildCameraGrid();
    refreshCameraTable();
    appendLog("已加载配置：" + configPath_);
}

void MainWindow::browseModel() {
    const QString path = QFileDialog::getOpenFileName(this, "选择 OpenVINO XML 模型", QString(), "OpenVINO XML (*.xml)");
    if (!path.isEmpty()) modelEdit_->setText(path);
}

void MainWindow::startMonitoring() {
    config_.inference.modelPath = modelEdit_->text().trimmed();
    config_.inference.device = deviceCombo_->currentText();
    config_.inference.inputSize = inputSizeSpin_->value();
    config_.wcs.enabled = wcsEnabledCheck_->isChecked();
    outputRoot_ = defaultOutputRoot();
    InferenceRuntimeConfig runtime;
    runtime.outputRoot = outputRoot_;
    runtime.previewFps = 10;
    inference_->configure(config_, runtime);
    if (config_.wcs.enabled) {
        wcsClient_->configure(config_.wcs);
        wcsClient_->start();
        heartbeatTimer_.start(config_.wcs.heartbeatMs);
    }
    inference_->start();
    updateButtons();
}

void MainWindow::stopMonitoring() {
    heartbeatTimer_.stop();
    if (inference_) inference_->stop();
    if (wcsClient_) wcsClient_->stop();
    updateButtons();
}

void MainWindow::handleFrameReady(const QString& cameraId, const QImage& image) {
    QLabel* tile = tileForCamera(cameraId);
    if (tile == nullptr) return;
    tile->setPixmap(QPixmap::fromImage(image).scaled(tile->size(), Qt::KeepAspectRatio, Qt::SmoothTransformation));
}

void MainWindow::handleSnapshot(const CameraRuntimeSnapshot& snapshot) {
    snapshots_[snapshot.cameraId] = snapshot;
    refreshCameraTable();
    if (wcsClient_ && config_.wcs.enabled) wcsClient_->sendCameraStatus(snapshot);
}

void MainWindow::handleFlowUpdate(const WcsFlowUpdate& update) { if (wcsClient_ && config_.wcs.enabled) wcsClient_->sendFlowUpdate(update); }
void MainWindow::handleJamOn(const WcsJamEvent& event) { appendLog("堵包报警：" + event.cameraId + "/" + event.roiId); if (wcsClient_ && config_.wcs.enabled) wcsClient_->sendJamOn(event); }
void MainWindow::handleJamOff(const WcsJamEvent& event) { appendLog("堵包解除：" + event.cameraId + "/" + event.roiId); if (wcsClient_ && config_.wcs.enabled) wcsClient_->sendJamOff(event); }
void MainWindow::handlePipelineLog(const QString& message) { appendLog(message); }
void MainWindow::sendHeartbeat() { if (wcsClient_ && config_.wcs.enabled) wcsClient_->sendHeartbeat(snapshots_.size(), config_.cameras.size(), 0.0); }

void MainWindow::rebuildCameraGrid() {
    QLayoutItem* child = nullptr;
    while ((child = grid_->takeAt(0)) != nullptr) {
        delete child->widget();
        delete child;
    }
    tiles_.clear();
    int index = 0;
    const int columns = config_.cameras.size() <= 4 ? 2 : (config_.cameras.size() <= 9 ? 3 : 4);
    for (const CameraConfig& camera : config_.cameras) {
        QLabel* label = new QLabel(camera.cameraId, this);
        label->setMinimumSize(320, 180);
        label->setAlignment(Qt::AlignCenter);
        label->setStyleSheet("background:#111;color:#ddd;border:1px solid #444;");
        tiles_.insert(camera.cameraId, label);
        grid_->addWidget(label, index / columns, index % columns);
        ++index;
    }
}

void MainWindow::refreshCameraTable() {
    cameraTable_->setRowCount(config_.cameras.size());
    rowByCamera_.clear();
    int row = 0;
    for (const CameraConfig& camera : config_.cameras) {
        rowByCamera_.insert(camera.cameraId, row);
        const CameraRuntimeSnapshot s = snapshots_.value(camera.cameraId);
        const QStringList cells = {camera.cameraId, camera.lineId, camera.beltId, s.status, QString::number(s.decodeFps, 'f', 1), QString::number(s.inferFps, 'f', 1), QString::number(s.totalCount), s.jamActive ? "JAM" : "OK"};
        for (int col = 0; col < cells.size(); ++col) cameraTable_->setItem(row, col, new QTableWidgetItem(cells[col]));
        if (tiles_.contains(camera.cameraId) && s.jamActive) tiles_[camera.cameraId]->setStyleSheet("background:#400;color:#fff;border:3px solid red;");
        ++row;
    }
}

void MainWindow::updateButtons() { stopButton_->setEnabled(inference_->isRunning()); startButton_->setEnabled(!inference_->isRunning()); }
void MainWindow::appendLog(const QString& message) { logEdit_->append(QDateTime::currentDateTime().toString("HH:mm:ss ") + message); }
QString MainWindow::defaultConfigPath() const { return QDir(QCoreApplication::applicationDirPath()).filePath("configs/cameras.json"); }
QString MainWindow::defaultOutputRoot() const { return QDir(QCoreApplication::applicationDirPath()).filePath("runtime/wcs_output"); }
QLabel* MainWindow::tileForCamera(const QString& cameraId) { return tiles_.value(cameraId, nullptr); }
