#include "app/MainWindow.h"

#include "app/AnnotationPanel.h"
#include "app/BatchProcessPanel.h"
#include "app/DatasetSplitPanel.h"
#include "app/DiagnosticsPanel.h"
#include "app/InferencePanel.h"
#include "app/ProjectPanel.h"
#include "app/TaskProgressPanel.h"

#include <QHBoxLayout>
#include <QListWidget>
#include <QStackedWidget>

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    setWindowTitle("数据集制作助手 V1.0");
    resize(1280, 820);
    auto* root = new QWidget(this);
    auto* layout = new QHBoxLayout(root);
    navigation_ = new QListWidget(root);
    navigation_->setFixedWidth(190);
    pages_ = new QStackedWidget(root);
    taskPanel_ = new TaskProgressPanel(root);

    auto* project = new ProjectPanel(root);
    auto* batch = new BatchProcessPanel(root);
    auto* annotation = new AnnotationPanel(root);
    auto* split = new DatasetSplitPanel(root);
    auto* diagnostics = new DiagnosticsPanel(root);
    auto* inference = new InferencePanel(root);

    addPage("工程", project);
    addPage("图片批处理", batch);
    addPage("标注转换", annotation);
    addPage("数据集划分", split);
    addPage("模型推理", inference);
    addPage("任务队列", taskPanel_);
    addPage("日志与诊断", diagnostics);

    layout->addWidget(navigation_);
    layout->addWidget(pages_, 1);
    setCentralWidget(root);

    setStyleSheet(
        "QWidget{background:#111820;color:#d9e2e5;font-family:'Microsoft YaHei UI';font-size:12px;}"
        "QListWidget{background:#18232b;border:0;padding:8px;}"
        "QListWidget::item{padding:10px;border-radius:4px;}"
        "QListWidget::item:selected{background:#2f6f73;color:white;}"
        "QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit,QTableWidget{background:#0b1116;border:1px solid #3d5159;border-radius:3px;padding:6px;color:#eef6f8;}"
        "QPushButton{background:#24343c;border:1px solid #50656d;border-radius:3px;padding:8px;color:#eef6f8;}"
        "QPushButton:hover{border-color:#d6a13a;background:#2d424b;}"
        "QProgressBar{border:1px solid #3d5159;border-radius:3px;text-align:center;background:#0b1116;}"
        "QProgressBar::chunk{background:#2f8c63;}"
        "QLabel#previewSurface{background:#0b1116;border:1px dashed #56717a;color:#8da4ac;}"
    );

    connect(navigation_, &QListWidget::currentRowChanged, pages_, &QStackedWidget::setCurrentIndex);
    auto logConnector = [this](const QString& message) { taskPanel_->appendLog(message); };
    connect(project, &ProjectPanel::logMessage, this, logConnector);
    connect(batch, &BatchProcessPanel::logMessage, this, logConnector);
    connect(annotation, &AnnotationPanel::logMessage, this, logConnector);
    connect(split, &DatasetSplitPanel::logMessage, this, logConnector);
    connect(inference, &InferencePanel::logMessage, this, logConnector);
    connect(diagnostics, &DiagnosticsPanel::logMessage, this, logConnector);
    connect(taskPanel_, &TaskProgressPanel::cancelRequested, batch, &BatchProcessPanel::cancelCurrentTask);
    connect(taskPanel_, &TaskProgressPanel::cancelRequested, annotation, &AnnotationPanel::cancelCurrentTask);
    connect(taskPanel_, &TaskProgressPanel::cancelRequested, split, &DatasetSplitPanel::cancelCurrentTask);
    connect(batch, &BatchProcessPanel::taskRunningChanged, taskPanel_, &TaskProgressPanel::setRunning);
    connect(annotation, &AnnotationPanel::taskRunningChanged, taskPanel_, &TaskProgressPanel::setRunning);
    connect(split, &DatasetSplitPanel::taskRunningChanged, taskPanel_, &TaskProgressPanel::setRunning);
    navigation_->setCurrentRow(0);
}

void MainWindow::addPage(const QString& name, QWidget* page) {
    navigation_->addItem(name);
    pages_->addWidget(page);
}
