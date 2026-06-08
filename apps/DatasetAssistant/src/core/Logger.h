#pragma once

#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>

class Logger {
public:
    explicit Logger(const std::filesystem::path& logDir);
    void info(const std::string& message);
    void warn(const std::string& message);
    void error(const std::string& message);
    void failedItem(const std::string& file, const std::string& message);
    std::filesystem::path logPath() const;

private:
    void write(const std::string& level, const std::string& message);

    std::filesystem::path logPath_;
    std::filesystem::path failedItemsPath_;
    std::ofstream log_;
    std::mutex mutex_;
};
