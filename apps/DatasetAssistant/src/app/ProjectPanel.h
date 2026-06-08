#pragma once

#include "model/ProjectConfig.h"

#include <QWidget>

class QComboBox;
class QLabel;
class QLineEdit;
class QPlainTextEdit;

class ProjectPanel : public QWidget {
    Q_OBJECT
public:
    explicit ProjectPanel(QWidget* parent = nullptr);

signals:
    void logMessage(const QString& message);

private:
    void createNewProject();
    void openProject();
    void saveProject();
    void chooseDirectory(QLineEdit* target, const QString& title);
    void loadProjectToForm(const QString& path);
    bool warnMissingPaths();
    ProjectConfig formToConfig(const QString& path) const;
    void setFormatCombo(QComboBox* combo, AnnotationFormat format);
    AnnotationFormat currentFormat(QComboBox* combo) const;

    QLineEdit* projectEdit_ = nullptr;
    QLineEdit* imageDirEdit_ = nullptr;
    QLineEdit* annotationDirEdit_ = nullptr;
    QLineEdit* outputDirEdit_ = nullptr;
    QComboBox* annotationFormatCombo_ = nullptr;
    QComboBox* outputFormatCombo_ = nullptr;
    QPlainTextEdit* classNamesEdit_ = nullptr;
    QLabel* statusLabel_ = nullptr;
};
