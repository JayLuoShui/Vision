#include "app/InferencePanel.h"

#include <QComboBox>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPushButton>
#include <QVBoxLayout>

#include <filesystem>

namespace {

DevicePolicy devicePolicyFromIndex(int index) {
    if (index == 1) {
        return DevicePolicy::Cpu;
    }
    if (index == 2) {
        return DevicePolicy::Gpu;
    }
    return DevicePolicy::Auto;
}

QString pathToQString(const std::filesystem::path& path) {
    return QString::fromUtf8(path.u8string().c_str());
}

std::filesystem::path toPath(const QString& text) {
    return std::filesystem::path(text.trimmed().toStdWString());
}

}  // namespace

InferencePanel::InferencePanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    auto* form = new QFormLayout();
    modelEdit_ = new QLineEdit(this);
    deviceCombo_ = new QComboBox(this);
    deviceCombo_->addItems({"自动", "CPU", "GPU"});
    providerLabel_ = new QLabel("未加载", this);

    auto* modelRow = new QWidget(this);
    auto* modelLayout = new QHBoxLayout(modelRow);
    modelLayout->setContentsMargins(0, 0, 0, 0);
    auto* choose = new QPushButton("选择", modelRow);
    modelLayout->addWidget(modelEdit_, 1);
    modelLayout->addWidget(choose);

    form->addRow("ONNX 模型", modelRow);
    form->addRow("设备策略", deviceCombo_);
    form->addRow("当前后端", providerLabel_);
    root->addLayout(form);
    auto* diagnose = new QPushButton("推理环境诊断", this);
    auto* load = new QPushButton("加载模型", this);
    root->addWidget(diagnose);
    root->addWidget(load);
    root->addStretch(1);
    connect(choose, &QPushButton::clicked, this, &InferencePanel::chooseModel);
    connect(diagnose, &QPushButton::clicked, this, &InferencePanel::runDiagnose);
    connect(load, &QPushButton::clicked, this, &InferencePanel::loadModel);
}

void InferencePanel::chooseModel() {
    const QString path = QFileDialog::getOpenFileName(this, "选择 ONNX 模型", QString(), "ONNX Model (*.onnx)");
    if (!path.isEmpty()) {
        modelEdit_->setText(path);
    }
}

void InferencePanel::runDiagnose() {
    const GpuDiagnostic diagnostic = engine_.diagnoseGpu();
    emit logMessage(QString("CPU 推理后端：%1").arg(diagnostic.cpuProviderAvailable ? "可用" : "不可用"));
    emit logMessage(QString("CUDA 推理后端：%1").arg(diagnostic.cudaProviderAvailable ? "可用" : "不可用"));
    if (!diagnostic.gpuName.empty()) {
        emit logMessage("GPU：" + QString::fromStdString(diagnostic.gpuName));
    }
    for (const auto& error : diagnostic.errors) {
        emit logMessage("诊断信息：" + QString::fromStdString(error));
    }
    if (!diagnostic.cudaProviderAvailable && diagnostic.cpuProviderAvailable) {
        emit logMessage("未检测到可用 CUDA 后端，可使用 CPU 模式运行。");
    }
}

void InferencePanel::loadModel() {
    const std::filesystem::path modelPath = toPath(modelEdit_->text());
    if (modelPath.empty() || !std::filesystem::exists(modelPath)) {
        QMessageBox::warning(this, "模型不存在", "请选择存在的 ONNX 模型文件。");
        return;
    }
    InferenceConfig config;
    config.modelPath = modelPath;
    config.devicePolicy = devicePolicyFromIndex(deviceCombo_->currentIndex());
    emit logMessage("开始加载 ONNX 模型：" + pathToQString(modelPath));
    if (!engine_.loadModel(modelPath, config)) {
        providerLabel_->setText("加载失败");
        if (config.devicePolicy == DevicePolicy::Gpu) {
            emit logMessage("GPU 模式不可用：当前电脑未检测到可用 NVIDIA CUDA 推理环境，请改用 CPU 或自动模式。");
        } else {
            emit logMessage("模型加载失败，请检查 ONNX 文件和运行库。");
        }
        return;
    }
    providerLabel_->setText(QString::fromStdString(engine_.providerName()));
    emit logMessage("模型加载完成，当前后端：" + QString::fromStdString(engine_.providerName()));
}
