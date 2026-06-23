#include "MainWindow.h"
#include "RuntimePaths.h"

#include <QApplication>
#include <QIcon>

int main(int argc, char* argv[]) {
    QApplication app(argc, argv);
    QApplication::setApplicationName("CVDS WCS多路视觉流量监测");
    QApplication::setOrganizationName("CVDS");
    QApplication::setApplicationVersion(RuntimePaths::versionText());
    QApplication::setWindowIcon(QIcon(":/branding/cogy_mark.png"));

    MainWindow window;
    window.showMaximized();
    return app.exec();
}
