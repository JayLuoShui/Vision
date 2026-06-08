#include "app/DatasetSplitPanel.h"

#include "core/ProjectManager.h"

#include <QCheckBox>
#include <QComboBox>
#include <QCoreApplication>
#include <QDoubleSpinBox>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QProcess>
#include <QPushButton>
#include <QSpinBox>
#include <QVBoxLayout>

#include <filesystem>

namespace fs = std::filesystem;

namespace {

fs::path toPath(const QString& text) {
    return fs::u8path(text.toStdString());
}

DatasetFormat datasetFormatFromIndex(int index) {
    switch (index) {
        case 1: return DatasetFormat::Coco;
        case 2: return DatasetFormat::Voc;
        case 3: return DatasetFormat::MaskPng;
        case 0:
        default: return DatasetFormat::Yolo;
    }
}

} // namespace

DatasetSplitPanel::DatasetSplitPanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    auto* form = new QFormLayout();
    projectEdit_ = new QLineEdit(this);
    formatCombo_ = new QComboBox(this);
    trainSpin_ = new QDoubleSpinBox(this);
    valSpin_ = new QDoubleSpinBox(this);
    testSpin_ = new QDoubleSpinBox(this);
    seedSpin_ = new QSpinBox(this);
    includeNegativeCheck_ = new QCheckBox(this);
    statusLabel_ = new QLabel(this);
    process_ = new QProcess(this);

    auto* projectRow = new QWidget(this);
    auto* projectLayout = new QHBoxLayout(projectRow);
    projectLayout->setContentsMargins(0, 0, 0, 0);
    auto* chooseProject = new QPushButton("选择", projectRow);
    projectLayout->addWidget(projectEdit_, 1);
    projectLayout->addWidget(chooseProject);

    formatCombo_->addItems({"YOLO", "COCO", "VOC", "mask PNG"});
    for (auto* spin : {trainSpin_, valSpin_, testSpin_}) {
        spin->setRange(0.0, 1.0);
        spin->setDecimals(2);
        spin->setSingleStep(0.05);
    }
    trainSpin_->setValue(0.70);
    valSpin_->setValue(0.20);
    testSpin_->setValue(0.10);
    seedSpin_->setRange(0, 2147483647);
    seedSpin_->setValue(20260528);
    includeNegativeCheck_->setChecked(true);

    form->addRow("工程文件", projectRow);
    form->addRow("导出格式", formatCombo_);
    form->addRow("train 比例", trainSpin_);
    form->addRow("val 比例", valSpin_);
    form->addRow("test 比例", testSpin_);
    form->addRow("随机种子", seedSpin_);
    form->addRow("包含负样本", includeNegativeCheck_);
    root->addLayout(form);
    auto* run = new QPushButton("开始划分数据集", this);
    root->addWidget(run);
    root->addWidget(statusLabel_);
    root->addStretch(1);

    connect(chooseProject, &QPushButton::clicked, this, &DatasetSplitPanel::chooseProjectFile);
    connect(run, &QPushButton::clicked, this, &DatasetSplitPanel::startSplit);
    connect(process_, &QProcess::readyReadStandardOutput, this, [this]() {
        const QString text = QString::fromUtf8(process_->readAllStandardOutput()).trimmed();
        if (!text.isEmpty()) {
            emit logMessage(text);
        }
    });
    connect(process_, &QProcess::readyReadStandardError, this, [this]() {
        const QString text = QString::fromUtf8(process_->readAllStandardError()).trimmed();
        if (!text.isEmpty()) {
            emit logMessage(text);
        }
    });
    connect(process_, &QProcess::finished, this, [this](int exitCode, QProcess::ExitStatus exitStatus) {
        const bool ok = exitStatus == QProcess::NormalExit && exitCode == 0;
        statusLabel_->setText(ok ? "数据集划分完成。" : "数据集划分失败，请查看日志。");
        emit logMessage(ok ? "数据集划分完成。" : "数据集划分失败，退出码：" + QString::number(exitCode));
        emit taskRunningChanged(false);
    });
}

void DatasetSplitPanel::chooseProjectFile() {
    const QString path = QFileDialog::getOpenFileName(this, "选择工程文件", QString(), "CVDS Project (*.cvdsproj.json *.json)");
    if (!path.isEmpty()) {
        projectEdit_->setText(path);
        emit logMessage("已选择划分工程：" + path);
    }
}

QString DatasetSplitPanel::currentProjectFile() const {
    return projectEdit_->text().trimmed();
}

void DatasetSplitPanel::applyFormToProject() {
    const QString projectFile = currentProjectFile();
    ProjectConfig config = ProjectManager::load(toPath(projectFile));
    config.split.format = datasetFormatFromIndex(formatCombo_->currentIndex());
    config.split.trainRatio = trainSpin_->value();
    config.split.valRatio = valSpin_->value();
    config.split.testRatio = testSpin_->value();
    config.split.seed = static_cast<std::uint32_t>(seedSpin_->value());
    config.split.includeNegative = includeNegativeCheck_->isChecked();
    config.split.classNames = config.classNames;
    ProjectManager::save(config, toPath(projectFile));
}

void DatasetSplitPanel::startSplit() {
    const QString projectFile = currentProjectFile();
    if (projectFile.isEmpty() || !fs::exists(toPath(projectFile))) {
        QMessageBox::warning(this, "缺少工程文件", "请先选择已保存的工程文件。");
        return;
    }
    const double totalRatio = trainSpin_->value() + valSpin_->value() + testSpin_->value();
    if (std::abs(totalRatio - 1.0) > 0.001) {
        QMessageBox::warning(this, "比例错误", "train、val、test 三项比例之和必须等于 1。");
        return;
    }
    if (process_->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "任务运行中", "当前数据集划分任务还在运行。");
        return;
    }
    applyFormToProject();
    statusLabel_->setText("数据集划分运行中...");
    emit logMessage("开始数据集划分：" + projectFile);
    emit taskRunningChanged(true);
    process_->start(QCoreApplication::applicationFilePath(), {"--split-dataset", projectFile});
}

void DatasetSplitPanel::cancelCurrentTask() {
    if (process_->state() == QProcess::NotRunning) {
        return;
    }
    emit logMessage("正在取消数据集划分任务。");
    process_->terminate();
    if (!process_->waitForFinished(1500)) {
        process_->kill();
    }
}
