#include "app/DiagnosticsPanel.h"

#include "core/RuntimePaths.h"

#include <QCoreApplication>
#include <QDesktopServices>
#include <QHBoxLayout>
#include <QLabel>
#include <QPlainTextEdit>
#include <QProcess>
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

void openDir(const std::filesystem::path& path) {
    QDesktopServices::openUrl(QUrl::fromLocalFile(pathToQString(path)));
}

} // namespace

DiagnosticsPanel::DiagnosticsPanel(QWidget* parent) : QWidget(parent) {
    auto* root = new QVBoxLayout(this);
    auto* buttons = new QHBoxLayout();
    auto* diagnoseButton = new QPushButton("运行环境诊断", this);
    auto* openLogsButton = new QPushButton("打开日志目录", this);
    auto* openDataButton = new QPushButton("打开用户数据目录", this);
    userDataLabel_ = new QLabel("用户数据目录：" + pathToQString(RuntimePaths::userDataDir()), this);
    logDirLabel_ = new QLabel("日志目录：" + pathToQString(RuntimePaths::logDir()), this);
    statusLabel_ = new QLabel("未运行诊断。", this);
    output_ = new QPlainTextEdit(this);
    process_ = new QProcess(this);

    output_->setReadOnly(true);
    buttons->addWidget(diagnoseButton);
    buttons->addWidget(openLogsButton);
    buttons->addWidget(openDataButton);
    buttons->addStretch(1);
    root->addLayout(buttons);
    root->addWidget(userDataLabel_);
    root->addWidget(logDirLabel_);
    root->addWidget(statusLabel_);
    root->addWidget(output_, 1);

    connect(diagnoseButton, &QPushButton::clicked, this, &DiagnosticsPanel::runDiagnose);
    connect(openLogsButton, &QPushButton::clicked, this, &DiagnosticsPanel::openLogDir);
    connect(openDataButton, &QPushButton::clicked, this, &DiagnosticsPanel::openUserDataDir);
    connect(process_, &QProcess::readyReadStandardOutput, this, [this]() {
        appendOutput(QString::fromUtf8(process_->readAllStandardOutput()));
    });
    connect(process_, &QProcess::readyReadStandardError, this, [this]() {
        appendOutput(QString::fromUtf8(process_->readAllStandardError()));
    });
    connect(process_, &QProcess::finished, this, [this](int exitCode, QProcess::ExitStatus exitStatus) {
        const bool ok = exitStatus == QProcess::NormalExit && exitCode == 0;
        statusLabel_->setText(ok ? "诊断完成。" : "诊断失败，请查看输出。");
        emit logMessage(ok ? "环境诊断完成。" : "环境诊断失败，退出码：" + QString::number(exitCode));
    });
}

void DiagnosticsPanel::runDiagnose() {
    if (process_->state() != QProcess::NotRunning) {
        appendOutput("诊断正在运行，请稍候。\n");
        return;
    }
    output_->clear();
    statusLabel_->setText("诊断运行中...");
    emit logMessage("开始环境诊断。");
    process_->start(QCoreApplication::applicationFilePath(), {"--diagnose"});
}

void DiagnosticsPanel::openLogDir() {
    openDir(RuntimePaths::logDir());
}

void DiagnosticsPanel::openUserDataDir() {
    openDir(RuntimePaths::userDataDir());
}

void DiagnosticsPanel::appendOutput(const QString& text) {
    const QString trimmed = text.trimmed();
    if (trimmed.isEmpty()) {
        return;
    }
    output_->appendPlainText(trimmed);
    emit logMessage(trimmed);
}
