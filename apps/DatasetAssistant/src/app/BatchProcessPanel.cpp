#include "app/BatchProcessPanel.h"

#include "core/ProjectManager.h"

#include <QCoreApplication>
#include <QCheckBox>
#include <QComboBox>
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

AnnotationFormat formatFromIndex(int index) {
    switch (index) {
        case 1: return AnnotationFormat::Coco;
        case 2: return AnnotationFormat::Voc;
        case 3: return AnnotationFormat::MaskPng;
        case 0:
        default: return AnnotationFormat::Yolo;
    }
}

int indexFromFormat(AnnotationFormat format) {
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

int indexFromExtension(const std::string& extension) {
    if (extension == ".png") return 1;
    if (extension == ".bmp") return 2;
    if (extension == ".webp") return 3;
    return 0;
}

} // namespace

BatchProcessPanel::BatchProcessPanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    auto* form = new QFormLayout();
    projectEdit_ = new QLineEdit(this);
    modeCombo_ = new QComboBox(this);
    outputFormatCombo_ = new QComboBox(this);
    outputImageExtCombo_ = new QComboBox(this);
    renamePrefixEdit_ = new QLineEdit(this);
    widthSpin_ = new QSpinBox(this);
    heightSpin_ = new QSpinBox(this);
    cropXSpin_ = new QSpinBox(this);
    cropYSpin_ = new QSpinBox(this);
    overlapXSpin_ = new QSpinBox(this);
    overlapYSpin_ = new QSpinBox(this);
    paddingRSpin_ = new QSpinBox(this);
    paddingGSpin_ = new QSpinBox(this);
    paddingBSpin_ = new QSpinBox(this);
    rotateSpin_ = new QSpinBox(this);
    renameStartSpin_ = new QSpinBox(this);
    renameDigitsSpin_ = new QSpinBox(this);
    jpegQualitySpin_ = new QSpinBox(this);
    keepVisibleRatioSpin_ = new QDoubleSpinBox(this);
    brightnessSpin_ = new QDoubleSpinBox(this);
    contrastSpin_ = new QDoubleSpinBox(this);
    horizontalFlipCheck_ = new QCheckBox(this);
    verticalFlipCheck_ = new QCheckBox(this);
    padEdgesCheck_ = new QCheckBox(this);
    brightnessContrastCheck_ = new QCheckBox(this);
    statusLabel_ = new QLabel(this);
    process_ = new QProcess(this);

    auto* projectRow = new QWidget(this);
    auto* projectLayout = new QHBoxLayout(projectRow);
    projectLayout->setContentsMargins(0, 0, 0, 0);
    auto* chooseProject = new QPushButton("选择", projectRow);
    projectLayout->addWidget(projectEdit_, 1);
    projectLayout->addWidget(chooseProject);

    for (auto* spin : {widthSpin_, heightSpin_}) {
        spin->setRange(1, 20000);
    }
    for (auto* spin : {cropXSpin_, cropYSpin_, overlapXSpin_, overlapYSpin_}) {
        spin->setRange(0, 20000);
    }
    for (auto* spin : {paddingRSpin_, paddingGSpin_, paddingBSpin_}) {
        spin->setRange(0, 255);
        spin->setValue(114);
    }
    rotateSpin_->setRange(0, 270);
    rotateSpin_->setSingleStep(90);
    renameStartSpin_->setRange(0, 999999999);
    renameDigitsSpin_->setRange(1, 12);
    jpegQualitySpin_->setRange(1, 100);
    keepVisibleRatioSpin_->setRange(0.0, 1.0);
    keepVisibleRatioSpin_->setDecimals(2);
    keepVisibleRatioSpin_->setSingleStep(0.05);
    brightnessSpin_->setRange(-255.0, 255.0);
    brightnessSpin_->setDecimals(1);
    contrastSpin_->setRange(0.01, 10.0);
    contrastSpin_->setDecimals(2);
    contrastSpin_->setSingleStep(0.05);
    widthSpin_->setValue(640);
    heightSpin_->setValue(640);
    renamePrefixEdit_->setText("img_");
    renameStartSpin_->setValue(1);
    renameDigitsSpin_->setValue(6);
    jpegQualitySpin_->setValue(95);
    keepVisibleRatioSpin_->setValue(0.20);
    contrastSpin_->setValue(1.0);
    modeCombo_->addItems({"固定 resize", "等比缩放 + padding", "裁剪 crop", "切片 tiling", "格式转换"});
    outputFormatCombo_->addItems({"YOLO", "COCO", "VOC", "mask PNG"});
    outputImageExtCombo_->addItems({"JPG", "PNG", "BMP", "WEBP"});
    form->addRow("工程文件", projectRow);
    form->addRow("处理模式", modeCombo_);
    form->addRow("导出标注格式", outputFormatCombo_);
    form->addRow("输出图片格式", outputImageExtCombo_);
    form->addRow("目标宽度", widthSpin_);
    form->addRow("目标高度", heightSpin_);
    form->addRow("裁剪 X", cropXSpin_);
    form->addRow("裁剪 Y", cropYSpin_);
    form->addRow("overlap X", overlapXSpin_);
    form->addRow("overlap Y", overlapYSpin_);
    form->addRow("边缘补齐 tile", padEdgesCheck_);
    form->addRow("可见比例阈值", keepVisibleRatioSpin_);
    form->addRow("padding R", paddingRSpin_);
    form->addRow("padding G", paddingGSpin_);
    form->addRow("padding B", paddingBSpin_);
    form->addRow("水平翻转", horizontalFlipCheck_);
    form->addRow("垂直翻转", verticalFlipCheck_);
    form->addRow("旋转角度", rotateSpin_);
    form->addRow("亮度/对比度", brightnessContrastCheck_);
    form->addRow("亮度", brightnessSpin_);
    form->addRow("对比度", contrastSpin_);
    form->addRow("命名前缀", renamePrefixEdit_);
    form->addRow("起始编号", renameStartSpin_);
    form->addRow("编号位数", renameDigitsSpin_);
    form->addRow("JPEG 质量", jpegQualitySpin_);
    root->addLayout(form);
    auto* run = new QPushButton("开始批处理", this);
    root->addWidget(run);
    root->addWidget(statusLabel_);
    root->addStretch(1);
    connect(chooseProject, &QPushButton::clicked, this, &BatchProcessPanel::chooseProjectFile);
    connect(run, &QPushButton::clicked, this, &BatchProcessPanel::startBatchProcess);
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
        statusLabel_->setText(ok ? "批处理完成。" : "批处理失败，请查看日志。");
        emit logMessage(ok ? "图片批处理完成。" : "图片批处理失败，退出码：" + QString::number(exitCode));
        emit taskRunningChanged(false);
    });
}

void BatchProcessPanel::chooseProjectFile() {
    const QString path = QFileDialog::getOpenFileName(this, "选择工程文件", QString(), "CVDS Project (*.cvdsproj.json *.json)");
    if (!path.isEmpty()) {
        projectEdit_->setText(path);
        loadProjectSettings();
        emit logMessage("已选择批处理工程：" + path);
    }
}

QString BatchProcessPanel::currentProjectFile() const {
    return projectEdit_->text().trimmed();
}

void BatchProcessPanel::applyFormToProject() {
    const QString projectFile = currentProjectFile();
    ProjectConfig config = ProjectManager::load(toPath(projectFile));
    const int mode = modeCombo_->currentIndex();
    config.outputAnnotationFormat = formatFromIndex(outputFormatCombo_->currentIndex());
    config.transform.enableResize = mode == 0 || mode == 1;
    config.transform.resize.keepAspect = mode == 1;
    config.transform.resize.width = widthSpin_->value();
    config.transform.resize.height = heightSpin_->value();
    config.transform.resize.paddingColor = cv::Scalar(paddingBSpin_->value(), paddingGSpin_->value(), paddingRSpin_->value());
    config.transform.enableCrop = mode == 2;
    config.transform.crop.x = cropXSpin_->value();
    config.transform.crop.y = cropYSpin_->value();
    config.transform.crop.width = widthSpin_->value();
    config.transform.crop.height = heightSpin_->value();
    config.transform.crop.keepVisibleRatio = keepVisibleRatioSpin_->value();
    config.transform.enableTiling = mode == 3;
    config.transform.tile.tileWidth = widthSpin_->value();
    config.transform.tile.tileHeight = heightSpin_->value();
    config.transform.tile.overlapX = overlapXSpin_->value();
    config.transform.tile.overlapY = overlapYSpin_->value();
    config.transform.tile.padEdges = padEdgesCheck_->isChecked();
    config.transform.tile.keepVisibleRatio = keepVisibleRatioSpin_->value();
    config.transform.flipHorizontal = horizontalFlipCheck_->isChecked();
    config.transform.flipVertical = verticalFlipCheck_->isChecked();
    config.transform.rotateDegrees = rotateSpin_->value();
    config.transform.enableBrightnessContrast = brightnessContrastCheck_->isChecked();
    config.transform.brightness = brightnessSpin_->value();
    config.transform.contrast = contrastSpin_->value();
    config.transform.rename.prefix = renamePrefixEdit_->text().trimmed().isEmpty()
        ? "img_"
        : renamePrefixEdit_->text().trimmed().toStdString();
    config.transform.rename.startIndex = renameStartSpin_->value();
    config.transform.rename.digits = renameDigitsSpin_->value();
    config.transform.rename.outputExtension = extensionFromIndex(outputImageExtCombo_->currentIndex()).toStdString();
    config.transform.rename.jpegQuality = jpegQualitySpin_->value();
    config.split.classNames = config.classNames;
    ProjectManager::save(config, toPath(projectFile));
}

void BatchProcessPanel::loadProjectSettings() {
    const QString projectFile = currentProjectFile();
    if (projectFile.isEmpty() || !fs::exists(toPath(projectFile))) {
        return;
    }
    const ProjectConfig config = ProjectManager::load(toPath(projectFile));
    outputFormatCombo_->setCurrentIndex(indexFromFormat(config.outputAnnotationFormat));
    outputImageExtCombo_->setCurrentIndex(indexFromExtension(config.transform.rename.outputExtension));
    widthSpin_->setValue(config.transform.enableTiling ? config.transform.tile.tileWidth : config.transform.resize.width);
    heightSpin_->setValue(config.transform.enableTiling ? config.transform.tile.tileHeight : config.transform.resize.height);
    cropXSpin_->setValue(config.transform.crop.x);
    cropYSpin_->setValue(config.transform.crop.y);
    overlapXSpin_->setValue(config.transform.tile.overlapX);
    overlapYSpin_->setValue(config.transform.tile.overlapY);
    padEdgesCheck_->setChecked(config.transform.tile.padEdges);
    keepVisibleRatioSpin_->setValue(config.transform.enableCrop ? config.transform.crop.keepVisibleRatio : config.transform.tile.keepVisibleRatio);
    paddingBSpin_->setValue(static_cast<int>(config.transform.resize.paddingColor[0]));
    paddingGSpin_->setValue(static_cast<int>(config.transform.resize.paddingColor[1]));
    paddingRSpin_->setValue(static_cast<int>(config.transform.resize.paddingColor[2]));
    horizontalFlipCheck_->setChecked(config.transform.flipHorizontal);
    verticalFlipCheck_->setChecked(config.transform.flipVertical);
    rotateSpin_->setValue(config.transform.rotateDegrees);
    brightnessContrastCheck_->setChecked(config.transform.enableBrightnessContrast);
    brightnessSpin_->setValue(config.transform.brightness);
    contrastSpin_->setValue(config.transform.contrast);
    renamePrefixEdit_->setText(QString::fromStdString(config.transform.rename.prefix));
    renameStartSpin_->setValue(config.transform.rename.startIndex);
    renameDigitsSpin_->setValue(config.transform.rename.digits);
    jpegQualitySpin_->setValue(config.transform.rename.jpegQuality);

    if (config.transform.enableTiling) {
        modeCombo_->setCurrentIndex(3);
    } else if (config.transform.enableCrop) {
        modeCombo_->setCurrentIndex(2);
    } else if (config.transform.enableResize && config.transform.resize.keepAspect) {
        modeCombo_->setCurrentIndex(1);
    } else if (config.transform.enableResize) {
        modeCombo_->setCurrentIndex(0);
    } else {
        modeCombo_->setCurrentIndex(4);
    }
}

void BatchProcessPanel::startBatchProcess() {
    const QString projectFile = currentProjectFile();
    if (projectFile.isEmpty() || !fs::exists(toPath(projectFile))) {
        QMessageBox::warning(this, "缺少工程文件", "请先选择已保存的工程文件。");
        return;
    }
    if (process_->state() != QProcess::NotRunning) {
        QMessageBox::information(this, "任务运行中", "当前批处理任务还在运行。");
        return;
    }
    applyFormToProject();
    statusLabel_->setText("批处理运行中...");
    emit logMessage("开始图片批处理：" + projectFile);
    emit taskRunningChanged(true);
    process_->start(QCoreApplication::applicationFilePath(), {"--batch-process", projectFile});
}

void BatchProcessPanel::cancelCurrentTask() {
    if (process_->state() == QProcess::NotRunning) {
        return;
    }
    emit logMessage("正在取消图片批处理任务。");
    process_->terminate();
    if (!process_->waitForFinished(1500)) {
        process_->kill();
    }
}
