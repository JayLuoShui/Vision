#pragma once

#include <QWidget>

class QComboBox;
class QLabel;
class QLineEdit;
class QProcess;

class AnnotationPanel : public QWidget {
    Q_OBJECT
public:
    explicit AnnotationPanel(QWidget* parent = nullptr);
    void cancelCurrentTask();
signals:
    void logMessage(const QString& message);
    void taskRunningChanged(bool running);

private:
    void chooseProjectFile();
    void startConversion();
    void applyFormToProject();
    void loadProjectSettings();
    QString currentProjectFile() const;

    QLineEdit* projectEdit_ = nullptr;
    QComboBox* inputFormatCombo_ = nullptr;
    QComboBox* outputFormatCombo_ = nullptr;
    QComboBox* outputImageExtCombo_ = nullptr;
    QLabel* statusLabel_ = nullptr;
    QProcess* process_ = nullptr;
};
