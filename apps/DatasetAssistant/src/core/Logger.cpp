#include "core/Logger.h"

#include <chrono>
#include <iomanip>
#include <sstream>

namespace fs = std::filesystem;

namespace {
std::string timestamp() {
    const auto now = std::chrono::system_clock::now();
    const auto time = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
    localtime_s(&tm, &time);
    std::ostringstream ss;
    ss << std::put_time(&tm, "%Y%m%d_%H%M%S");
    return ss.str();
}
}  // namespace

Logger::Logger(const fs::path& logDir) {
    fs::create_directories(logDir);
    logPath_ = logDir / ("app_" + timestamp() + ".log");
    failedItemsPath_ = logDir / "failed_items.csv";
    log_.open(logPath_, std::ios::app);
}

void Logger::info(const std::string& message) {
    write("INFO", message);
}

void Logger::warn(const std::string& message) {
    write("WARN", message);
}

void Logger::error(const std::string& message) {
    write("ERROR", message);
}

void Logger::failedItem(const std::string& file, const std::string& message) {
    std::lock_guard<std::mutex> lock(mutex_);
    std::ofstream out(failedItemsPath_, std::ios::app);
    out << '"' << file << "\",\"" << message << "\"\n";
}

fs::path Logger::logPath() const {
    return logPath_;
}

void Logger::write(const std::string& level, const std::string& message) {
    std::lock_guard<std::mutex> lock(mutex_);
    if (log_) {
        log_ << "[" << level << "] " << message << "\n";
        log_.flush();
    }
}
