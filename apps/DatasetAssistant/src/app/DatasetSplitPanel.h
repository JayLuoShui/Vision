#pragma once

#include <QWidget>

class QCheckBox;
class QComboBox;
class QDoubleSpinBox;
class QLabel;
class QLineEdit;
class QProcess;
class QSpinBox;

class DatasetSplitPanel : public QWidget {
    Q_OBJECT
public:
    explicit DatasetSplitPanel(QWidget* parent = nullptr);
    void cancelCurrentTask();

signals:
    void logMessage(const QString& message);
    void taskRunningChanged(bool running);

private:
    void chooseProjectFile();
    void startSplit();
    void applyFormToProject();
    QString currentProjectFile() const;

    QLineEdit* projectEdit_ = nullptr;
    QComboBox* formatCombo_ = nullptr;
    QDoubleSpinBox* trainSpin_ = nullptr;
    QDoubleSpinBox* valSpin_ = nullptr;
    QDoubleSpinBox* testSpin_ = nullptr;
    QSpinBox* seedSpin_ = nullptr;
    QCheckBox* includeNegativeCheck_ = nullptr;
    QLabel* statusLabel_ = nullptr;
    QProcess* process_ = nullptr;
};
