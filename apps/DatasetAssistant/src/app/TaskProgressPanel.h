#pragma once

#include <QWidget>

class QPlainTextEdit;
class QProgressBar;

class TaskProgressPanel : public QWidget {
    Q_OBJECT
public:
    explicit TaskProgressPanel(QWidget* parent = nullptr);
    void appendLog(const QString& text);
    void setRunning(bool running);

signals:
    void cancelRequested();

private:
    void openDefaultOutputDir();
    void openLogDir();

    QProgressBar* progress_ = nullptr;
    QPlainTextEdit* log_ = nullptr;
};
