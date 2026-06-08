#include "app/AnnotationPanel.h"

#include "core/ProjectManager.h"

#include <QComboBox>
#include <QCoreApplication>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QProcess>
#include <QPushButton>
#include <QVBoxLayout>

#include <filesystem>

namespace fs = std::filesystem;

namespace {

fs::path toPath(const QString& text) {
    return fs::u8path(text.toStdString());
}

AnnotationFormat annotationFormatFromIndex(int index) {
    switch (index) {
        case 1: return AnnotationFormat::Coco;
        case 2: return AnnotationFormat::Voc;
        case 3: return AnnotationFormat::MaskPng;
        case 0:
        default: return AnnotationFormat::Yolo;
    }
}

int indexFromAnnotationFormat(AnnotationFormat format) {
    switch (format) {
        case AnnotationFormat::Coco: return 1;
        case AnnotationFormat::Voc: return 2;
        case AnnotationFormat::MaskPng: return 3;
        case AnnotationFormat::Yolo:
        default: return 0;
    }
}

QString extensionFromIndex(int index) {
    switch (index) {
        case 1: return ".png";
        case 2: return ".bmp";
        case 3: return ".webp";
        case 0:
        default: return ".jpg";
    }
}

} // namespace

AnnotationPanel::AnnotationPanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    auto* form = new QFormLayout();
    projectEdit_ = new QLineEdit(this);
    inputFormatCombo_ = new QComboBox(this);
    outputFormatCombo_ = new QComboBox(this);
    outputImageExtCombo_ = new QComboBox(this);
    statusLabel_ = new QLabel(this);
    process_ = new QProcess(this);

    auto* projectRow = new QWidget(this);
    auto* projectLayout = new QHBoxLayout(projectRow);
    projectLayout->setContentsMargins(0, 0, 0, 0);
    auto* chooseProject = new QPushButton("选择", projectRow);
    projectLayout->addWidget(projectEdit_, 1);
    projectLayout->addWidget(chooseProject);

    inputFormatCombo_->addItems({"YOLO", "COCO", "VOC", "mask PNG"});
    outputFormatCombo_->addItems({"YOLO", "COCO", "VOC", "mask PNG"});
    outputImageExtCombo_->addItems({"JPG", "PNG", "BMP", "WEBP"});

    form->addRow("工程文件", projectRow);
    form->addRow("导入格式", inputFormatCombo_);
    form->addRow("导出格式", outputFormatCombo_);
    form->addRow("输出图片格式", outputImageExtCombo_);
    root->addLayout(form);
    auto* run = new QPushButton("转换标注", this);
    root->addWidget(run);
    root->addWidget(statusLabel_);
    root->addStretch(1);

    connect(chooseProject, &QPushButton::clicked, this, &AnnotationPanel::chooseProjectFile);
    connect(run, &QPushButton::clicked, this, &AnnotationPanel::startConversion);
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
        statusLabel_->setText(ok ? "标注转换完成。" : "标注转换失败，请查看日志。");
        emit logMessage(ok ? "标注转换完成。" : "标注转换失败，退出码：" + QString::number(exitCode));
        emit taskRunningChanged(false);
    });
}

void AnnotationPanel::chooseProjectFile() {
    const QString path = QFileDialog::getOpenFileName(this, "选择工程文件", QString(), "CVDS Project (*.cvdsproj.json *.json)");
    if (!path.isEmpty()) {
        projectEdit_->setText(path);
        loadProjectSettings();
        emit logMessage("已选择标注转换工程：" + path);
    }
}

QString AnnotationPanel::currentProjectFile() const {
    return projectEdit_->text().trimmed();
}

void AnnotationPanel::loadProjectSettings() {
    const QString projectFile = currentProjectFile();
    if (projectFile.isEmpty() || !fs::exists(toPath(projectFile))) {
        return;
    }
    const ProjectConfig config = ProjectManager::load(toPath(projectFile));
    inputFormatCombo_->setCurrentIndex(indexFromAnnotationFormat(config.annotationFormat));
    outputFormatCombo_->setCurrentIndex(indexFromAnnotationFormat(config.outputAnnotationFormat));
}

void AnnotationPanel::applyFormToProject() {
    const QString projectFile = currentProjectFile();
    ProjectConfig config = ProjectManager::load(toPath(projectFile));
    config.annotationFormat = annotationFormatFromIndex(inputFormatCombo_->currentIndex());
    config.outputAnnotationFormat = annotationFormatFromIndex(outputFormatCombo_->currentIndex());
    config.transform.enableResize = false;
    config.transform.enableCrop = false;
    config.transform.enableTiling = false;
    config.transform.flipHorizontal = false;
    config.transform.flipVertical = false;
    config.transform.rotateDegrees = 0;
    config.transform.enableBrightnessContrast = false;
    config.transform.rename.outputExtension = extensionFromIndex(outputImageExtCombo_->currentIndex()).toStdString();
    config.split.classNames = config.classNames;
    ProjectManager::save(config, toPath(projectFile));
}

void AnnotationPanel::startConversion() {
    const QString projectFile = currentProjectFile();
    if (projectFile.isEmpty() || !fs::exists(toPath(projectFile))) {
        QMessageBox::warning(this, "缺少工程文件", "请先选择已保存的工程文件。");
        return;
    }
    const ProjectConfig config = ProjectManager::load(toPath(projectFile));
    if (config.imageInputDir.empty() || !fs::exists(config.imageInputDir)) {
        QMessageBox::warning(this, "缺少图片目录", "工程里的输入图片目录不存在，请先在工程页重新选择。");
        return;
    }
    if (config.annotationDir.empty() || !fs::exists(config.annotationDir)) {
        QMessageBox::warning(this, "缺少标注目录", "工程里的标注目录不存在，请先在工程页重新选择。");
        return;
    }
    if (process_->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "任务运行中", "当前标注转换任务还在运行。");
        return;
    }
    applyFormToProject();
    statusLabel_->setText("标注转换运行中...");
    emit logMessage("开始标注转换：" + projectFile);
    emit taskRunningChanged(true);
    process_->start(QCoreApplication::applicationFilePath(), {"--batch-process", projectFile});
}

void AnnotationPanel::cancelCurrentTask() {
    if (process_->state() == QProcess::NotRunning) {
        return;
    }
    emit logMessage("正在取消标注转换任务。");
    process_->terminate();
    if (!process_->waitForFinished(1500)) {
        process_->kill();
    }
}
