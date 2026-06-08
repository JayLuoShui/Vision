#include "app/TaskProgressPanel.h"

#include "core/RuntimePaths.h"

#include <QDateTime>
#include <QDesktopServices>
#include <QHBoxLayout>
#include <QPlainTextEdit>
#include <QProgressBar>
#include <QPushButton>
#include <QUrl>
#include <QVBoxLayout>

namespace {

QString pathToQString(const std::filesystem::path& path) {
#ifdef _WIN32
    return QString::fromStdWString(path.wstring());
#else
    return QString::fromStdString(path.string());
#endif
}

} // namespace

TaskProgressPanel::TaskProgressPanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    progress_ = new QProgressBar(this);
    progress_->setRange(0, 100);
    progress_->setValue(0);
    log_ = new QPlainTextEdit(this);
    log_->setReadOnly(true);
    auto* buttons = new QHBoxLayout();
    auto* cancel = new QPushButton("取消当前任务", this);
    auto* openOutput = new QPushButton("打开默认输出目录", this);
    auto* openLogs = new QPushButton("打开日志目录", this);
    auto* clear = new QPushButton("清空日志", this);
    buttons->addWidget(cancel);
    buttons->addWidget(openOutput);
    buttons->addWidget(openLogs);
    buttons->addWidget(clear);
    buttons->addStretch(1);
    root->addWidget(progress_);
    root->addLayout(buttons);
    root->addWidget(log_, 1);

    connect(cancel, &QPushButton::clicked, this, [this]() {
        appendLog("已请求取消当前后台任务。");
        emit cancelRequested();
    });
    connect(openOutput, &QPushButton::clicked, this, &TaskProgressPanel::openDefaultOutputDir);
    connect(openLogs, &QPushButton::clicked, this, &TaskProgressPanel::openLogDir);
    connect(clear, &QPushButton::clicked, log_, &QPlainTextEdit::clear);
}

void TaskProgressPanel::appendLog(const QString& text) {
    log_->appendPlainText(QDateTime::currentDateTime().toString("HH:mm:ss ") + text);
}

void TaskProgressPanel::setRunning(bool running) {
    if (running) {
        progress_->setRange(0, 0);
    } else {
        progress_->setRange(0, 100);
        progress_->setValue(0);
    }
}

void TaskProgressPanel::openDefaultOutputDir() {
    QDesktopServices::openUrl(QUrl::fromLocalFile(pathToQString(RuntimePaths::defaultOutputDir())));
}

void TaskProgressPanel::openLogDir() {
    QDesktopServices::openUrl(QUrl::fromLocalFile(pathToQString(RuntimePaths::logDir())));
}
