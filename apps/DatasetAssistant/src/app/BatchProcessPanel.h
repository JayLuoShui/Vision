#pragma once

#include <QWidget>

class QCheckBox;
class QComboBox;
class QDoubleSpinBox;
class QLabel;
class QLineEdit;
class QProcess;
class QSpinBox;

class BatchProcessPanel : public QWidget {
    Q_OBJECT
public:
    explicit BatchProcessPanel(QWidget* parent = nullptr);
    void cancelCurrentTask();
signals:
    void logMessage(const QString& message);
    void taskRunningChanged(bool running);

private:
    void chooseProjectFile();
    void startBatchProcess();
    void applyFormToProject();
    void loadProjectSettings();
    QString currentProjectFile() const;

    QLineEdit* projectEdit_ = nullptr;
    QComboBox* modeCombo_ = nullptr;
    QComboBox* outputFormatCombo_ = nullptr;
    QComboBox* outputImageExtCombo_ = nullptr;
    QLineEdit* renamePrefixEdit_ = nullptr;
    QSpinBox* widthSpin_ = nullptr;
    QSpinBox* heightSpin_ = nullptr;
    QSpinBox* cropXSpin_ = nullptr;
    QSpinBox* cropYSpin_ = nullptr;
    QSpinBox* overlapXSpin_ = nullptr;
    QSpinBox* overlapYSpin_ = nullptr;
    QSpinBox* paddingRSpin_ = nullptr;
    QSpinBox* paddingGSpin_ = nullptr;
    QSpinBox* paddingBSpin_ = nullptr;
    QSpinBox* rotateSpin_ = nullptr;
    QSpinBox* renameStartSpin_ = nullptr;
    QSpinBox* renameDigitsSpin_ = nullptr;
    QSpinBox* jpegQualitySpin_ = nullptr;
    QDoubleSpinBox* keepVisibleRatioSpin_ = nullptr;
    QDoubleSpinBox* brightnessSpin_ = nullptr;
    QDoubleSpinBox* contrastSpin_ = nullptr;
    QCheckBox* horizontalFlipCheck_ = nullptr;
    QCheckBox* verticalFlipCheck_ = nullptr;
    QCheckBox* padEdgesCheck_ = nullptr;
    QCheckBox* brightnessContrastCheck_ = nullptr;
    QLabel* statusLabel_ = nullptr;
    QProcess* process_ = nullptr;
};
