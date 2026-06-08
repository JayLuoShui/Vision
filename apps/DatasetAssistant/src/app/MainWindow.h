#pragma once

#include <QMainWindow>

class QListWidget;
class QStackedWidget;
class TaskProgressPanel;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);

private:
    void addPage(const QString& name, QWidget* page);

    QListWidget* navigation_ = nullptr;
    QStackedWidget* pages_ = nullptr;
    TaskProgressPanel* taskPanel_ = nullptr;
};
