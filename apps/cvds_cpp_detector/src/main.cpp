#include "MainWindow.h"
#include "RuntimePaths.h"

#include <QApplication>

int main(int argc, char* argv[]) {
    QApplication app(argc, argv);
    QApplication::setApplicationName("CVDS包裹流量检测工具");
    QApplication::setOrganizationName("CVDS");
    QApplication::setApplicationVersion(RuntimePaths::versionText());

    MainWindow window;
    window.show();
    return app.exec();
}
