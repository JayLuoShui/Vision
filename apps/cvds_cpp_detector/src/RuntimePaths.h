#pragma once

#include <QString>

namespace RuntimePaths {

QString appDir();
QString runtimeDir();
QString workerExePath();
QString scriptsDir();
QString defaultWeightsDir();
QString defaultOutputDir();
QString writableAppDataDir();
QString configDir();
QString defaultRegionsConfigPath();
QString regionsExamplePath();
QString trackerConfigPath();
QString docsDir();
QString versionFilePath();
QString versionText();

}  // namespace RuntimePaths
