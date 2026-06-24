#pragma once

#include <QString>

namespace RuntimePaths {

QString appDir();
QString defaultWeightsDir();
QString defaultOutputDir();
QString writableAppDataDir();
QString configDir();
QString defaultRegionsConfigPath();
QString regionsExamplePath();
QString docsDir();
QString versionFilePath();
QString versionText();

}  // namespace RuntimePaths
