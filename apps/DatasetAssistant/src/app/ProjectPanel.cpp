#include "app/ProjectPanel.h"

#include "core/ProjectManager.h"
#include "core/RuntimePaths.h"

#include <QComboBox>
#include <QFileDialog>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QRegularExpression>
#include <QVBoxLayout>

#include <filesystem>

namespace fs = std::filesystem;

namespace {

QString toQString(const fs::path& path) {
    return QString::fromUtf8(path.u8string().c_str());
}

fs::path toPath(const QString& text) {
    return fs::u8path(text.toStdString());
}

QString classesToText(const std::vector<std::string>& classes) {
    QStringList lines;
    for (const auto& name : classes) {
        lines << QString::fromUtf8(name.c_str());
    }
    return lines.join("\n");
}

std::vector<std::string> classesFromText(const QString& text) {
    std::vector<std::string> classes;
    for (QString part : text.split(QRegularExpression("[,;\\n\\r\\t]+"), Qt::SkipEmptyParts)) {
        part = part.trimmed();
        if (!part.isEmpty()) {
            classes.push_back(part.toUtf8().toStdString());
        }
    }
    if (classes.empty()) {
        classes.push_back("object");
    }
    return classes;
}

QWidget* makePathRow(QWidget* parent, QLineEdit* edit, const QString& buttonText, const std::function<void()>& onClick) {
    auto* row = new QWidget(parent);
    auto* layout = new QHBoxLayout(row);
    layout->setContentsMargins(0, 0, 0, 0);
    auto* button = new QPushButton(buttonText, row);
    layout->addWidget(edit, 1);
    layout->addWidget(button);
    QObject::connect(button, &QPushButton::clicked, row, onClick);
    return row;
}

} // namespace

ProjectPanel::ProjectPanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    auto* form = new QFormLayout();
    projectEdit_ = new QLineEdit(this);
    imageDirEdit_ = new QLineEdit(this);
    annotationDirEdit_ = new QLineEdit(this);
    outputDirEdit_ = new QLineEdit(this);
    annotationFormatCombo_ = new QComboBox(this);
    outputFormatCombo_ = new QComboBox(this);
    classNamesEdit_ = new QPlainTextEdit(this);
    statusLabel_ = new QLabel(this);
    statusLabel_->setWordWrap(true);
    annotationFormatCombo_->addItems({"YOLO", "COCO", "VOC", "mask PNG"});
    outputFormatCombo_->addItems({"YOLO", "COCO", "VOC", "mask PNG"});
    classNamesEdit_->setPlaceholderText("每行一个类别名，例如：\npackage\nbox");
    classNamesEdit_->setMinimumHeight(88);
    outputDirEdit_->setText(toQString(RuntimePaths::defaultOutputDir()));
    form->addRow("工程文件", makePathRow(this, projectEdit_, "选择", [this]() {
        const QString path = QFileDialog::getSaveFileName(this, "选择工程文件", QString(), "CVDS Project (*.cvdsproj.json)");
        if (!path.isEmpty()) {
            projectEdit_->setText(path);
        }
    }));
    form->addRow("图片目录", makePathRow(this, imageDirEdit_, "选择", [this]() { chooseDirectory(imageDirEdit_, "选择图片目录"); }));
    form->addRow("标注目录", makePathRow(this, annotationDirEdit_, "选择", [this]() { chooseDirectory(annotationDirEdit_, "选择标注目录"); }));
    form->addRow("输出目录", makePathRow(this, outputDirEdit_, "选择", [this]() { chooseDirectory(outputDirEdit_, "选择输出目录"); }));
    form->addRow("当前标注格式", annotationFormatCombo_);
    form->addRow("默认导出格式", outputFormatCombo_);
    form->addRow("类别列表", classNamesEdit_);
    root->addLayout(form);
    auto* buttons = new QHBoxLayout();
    auto* newButton = new QPushButton("新建工程", this);
    auto* openButton = new QPushButton("打开工程", this);
    auto* saveButton = new QPushButton("保存工程", this);
    buttons->addWidget(newButton);
    buttons->addWidget(openButton);
    buttons->addWidget(saveButton);
    root->addLayout(buttons);
    root->addWidget(statusLabel_);
    root->addStretch(1);
    connect(openButton, &QPushButton::clicked, this, &ProjectPanel::openProject);
    connect(newButton, &QPushButton::clicked, this, &ProjectPanel::createNewProject);
    connect(saveButton, &QPushButton::clicked, this, &ProjectPanel::saveProject);
    createNewProject();
}

void ProjectPanel::createNewProject() {
    imageDirEdit_->clear();
    annotationDirEdit_->clear();
    outputDirEdit_->setText(toQString(RuntimePaths::defaultOutputDir()));
    setFormatCombo(annotationFormatCombo_, AnnotationFormat::Yolo);
    setFormatCombo(outputFormatCombo_, AnnotationFormat::Yolo);
    classNamesEdit_->setPlainText("object");
    statusLabel_->setText("新工程已就绪。输出目录默认写入用户目录，不写安装目录。");
    emit logMessage("已新建空工程。");
}

void ProjectPanel::openProject() {
    const QString path = QFileDialog::getOpenFileName(this, "打开工程", QString(), "CVDS Project (*.cvdsproj.json *.json)");
    if (!path.isEmpty()) {
        loadProjectToForm(path);
    }
}

void ProjectPanel::saveProject() {
    QString path = projectEdit_->text().trimmed();
    if (path.isEmpty()) {
        path = QFileDialog::getSaveFileName(this, "保存工程", QString(), "CVDS Project (*.cvdsproj.json)");
        if (path.isEmpty()) {
            return;
        }
        projectEdit_->setText(path);
    }

    ProjectConfig config = formToConfig(path);

    if (!ProjectManager::save(config, toPath(path))) {
        QMessageBox::warning(this, "保存失败", "工程文件保存失败，请检查路径和权限。");
        statusLabel_->setText("工程保存失败。");
        emit logMessage("工程保存失败：" + path);
        return;
    }
    statusLabel_->setText("工程已保存：" + path);
    emit logMessage("工程已保存：" + path);
}

void ProjectPanel::chooseDirectory(QLineEdit* target, const QString& title) {
    const QString path = QFileDialog::getExistingDirectory(this, title);
    if (!path.isEmpty()) {
        target->setText(path);
    }
}

void ProjectPanel::loadProjectToForm(const QString& path) {
    const ProjectConfig config = ProjectManager::load(toPath(path));
    projectEdit_->setText(path);
    imageDirEdit_->setText(toQString(config.imageInputDir));
    annotationDirEdit_->setText(toQString(config.annotationDir));
    outputDirEdit_->setText(toQString(config.outputDir.empty() ? RuntimePaths::defaultOutputDir() : config.outputDir));
    setFormatCombo(annotationFormatCombo_, config.annotationFormat);
    setFormatCombo(outputFormatCombo_, config.outputAnnotationFormat);
    classNamesEdit_->setPlainText(classesToText(config.classNames));
    const bool hasMissingPaths = warnMissingPaths();
    statusLabel_->setText(hasMissingPaths ? "工程已打开，但部分历史路径不存在，请重新选择。" : "工程已打开。");
    emit logMessage("工程已打开：" + path);
}

bool ProjectPanel::warnMissingPaths() {
    QStringList missing;
    if (!imageDirEdit_->text().trimmed().isEmpty() && !fs::exists(toPath(imageDirEdit_->text().trimmed()))) {
        missing << "图片目录";
    }
    if (!annotationDirEdit_->text().trimmed().isEmpty() && !fs::exists(toPath(annotationDirEdit_->text().trimmed()))) {
        missing << "标注目录";
    }
    if (!outputDirEdit_->text().trimmed().isEmpty() && !fs::exists(toPath(outputDirEdit_->text().trimmed()))) {
        missing << "输出目录";
    }
    if (missing.isEmpty()) {
        return false;
    }
    QMessageBox::warning(this, "路径不存在", "以下路径不存在，请重新选择：\n" + missing.join("\n"));
    return true;
}

ProjectConfig ProjectPanel::formToConfig(const QString& path) const {
    ProjectConfig config = fs::exists(toPath(path))
        ? ProjectManager::load(toPath(path))
        : ProjectManager::createDefault(toPath(path));
    config.projectFile = toPath(path);
    config.imageInputDir = toPath(imageDirEdit_->text().trimmed());
    config.annotationDir = toPath(annotationDirEdit_->text().trimmed());
    config.outputDir = outputDirEdit_->text().trimmed().isEmpty()
        ? RuntimePaths::defaultOutputDir()
        : toPath(outputDirEdit_->text().trimmed());
    config.annotationFormat = currentFormat(annotationFormatCombo_);
    config.outputAnnotationFormat = currentFormat(outputFormatCombo_);
    config.classNames = classesFromText(classNamesEdit_->toPlainText());
    config.split.classNames = config.classNames;
    return config;
}

void ProjectPanel::setFormatCombo(QComboBox* combo, AnnotationFormat format) {
    switch (format) {
        case AnnotationFormat::Coco:
            combo->setCurrentIndex(1);
            break;
        case AnnotationFormat::Voc:
            combo->setCurrentIndex(2);
            break;
        case AnnotationFormat::MaskPng:
            combo->setCurrentIndex(3);
            break;
        case AnnotationFormat::Yolo:
        default:
            combo->setCurrentIndex(0);
            break;
    }
}

AnnotationFormat ProjectPanel::currentFormat(QComboBox* combo) const {
    switch (combo->currentIndex()) {
        case 1: return AnnotationFormat::Coco;
        case 2: return AnnotationFormat::Voc;
        case 3: return AnnotationFormat::MaskPng;
        case 0:
        default: return AnnotationFormat::Yolo;
    }
}
