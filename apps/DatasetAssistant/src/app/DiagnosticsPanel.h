#pragma once

#include <QWidget>

class QLabel;
class QPlainTextEdit;
class QProcess;

class DiagnosticsPanel : public QWidget {
    Q_OBJECT
public:
    explicit DiagnosticsPanel(QWidget* parent = nullptr);

signals:
    void logMessage(const QString& message);

private:
    void runDiagnose();
    void openLogDir();
    void openUserDataDir();
    void appendOutput(const QString& text);

    QLabel* userDataLabel_ = nullptr;
    QLabel* logDirLabel_ = nullptr;
    QLabel* statusLabel_ = nullptr;
    QPlainTextEdit* output_ = nullptr;
    QProcess* process_ = nullptr;
};
