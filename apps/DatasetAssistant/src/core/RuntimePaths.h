#pragma once

#include <filesystem>
#include <string>

class RuntimePaths {
public:
    static std::filesystem::path appDir();
    static std::filesystem::path userDataDir();
    static std::filesystem::path logDir();
    static std::filesystem::path defaultOutputDir();
    static bool isWritableDirectory(const std::filesystem::path& dir);
    static std::string version();
};
