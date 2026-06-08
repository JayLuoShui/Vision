#pragma once

#include "core/InferenceEngine.h"

#include <QWidget>

class QComboBox;
class QLabel;
class QLineEdit;

class InferencePanel : public QWidget {
    Q_OBJECT
public:
    explicit InferencePanel(QWidget* parent = nullptr);
signals:
    void logMessage(const QString& message);

private:
    void chooseModel();
    void runDiagnose();
    void loadModel();

    QLineEdit* modelEdit_ = nullptr;
    QComboBox* deviceCombo_ = nullptr;
    QLabel* providerLabel_ = nullptr;
    InferenceEngine engine_;
};
