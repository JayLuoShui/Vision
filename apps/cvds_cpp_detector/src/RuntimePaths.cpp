#include "RuntimePaths.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QStandardPaths>
#include <QStringList>
#include <QTextStream>

namespace RuntimePaths {

QString appDir() {
    return QDir::cleanPath(QCoreApplication::applicationDirPath());
}

QString runtimeDir() {
    return QDir(appDir()).filePath("runtime");
}

QString workerExePath() {
    return QDir(runtimeDir()).filePath("cvds_detector_worker.exe");
}

QString scriptsDir() {
    return QDir(appDir()).filePath("scripts");
}

QString defaultWeightsDir() {
    return QDir(appDir()).filePath("weights");
}

QString writableAppDataDir() {
    QString path = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    if (path.trimmed().isEmpty()) {
        path = QDir::home().filePath("AppData/Local/CVDS/CVDS包裹流量检测工具");
    }
    QDir().mkpath(path);
    return QDir::cleanPath(path);
}

QString defaultOutputDir() {
    const QString path = QDir(writableAppDataDir()).filePath("runs");
    QDir().mkpath(path);
    return path;
}

QString trackerConfigPath() {
    return QDir(appDir()).filePath("configs/bytetrack.yaml");
}

QString docsDir() {
    return QDir(appDir()).filePath("docs");
}

QString versionFilePath() {
    return QDir(appDir()).filePath("VERSION.txt");
}

QString versionText() {
    QFile file(versionFilePath());
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return QCoreApplication::applicationVersion().trimmed().isEmpty()
            ? QStringLiteral("dev")
            : QCoreApplication::applicationVersion().trimmed();
    }
    QTextStream stream(&file);
    const QString version = stream.readLine().trimmed();
    return version.isEmpty() ? QStringLiteral("dev") : version;
}

}  // namespace RuntimePaths
