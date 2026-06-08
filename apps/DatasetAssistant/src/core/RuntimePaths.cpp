#include "core/RuntimePaths.h"

#ifdef _WIN32
#include <windows.h>
#endif

#include <cstdlib>
#include <fstream>
#include <system_error>

namespace fs = std::filesystem;

fs::path RuntimePaths::appDir() {
#ifdef _WIN32
    std::wstring buffer(MAX_PATH, L'\0');
    DWORD size = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    while (size == buffer.size()) {
        buffer.resize(buffer.size() * 2);
        size = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    }
    if (size > 0) {
        buffer.resize(size);
        return fs::path(buffer).parent_path();
    }
#endif
    return fs::current_path();
}

fs::path RuntimePaths::userDataDir() {
    const char* local = std::getenv("LOCALAPPDATA");
    fs::path base = local != nullptr ? fs::path(local) : fs::temp_directory_path();
    fs::path dir = base / "CVDS" / "DatasetAssistant";
    fs::create_directories(dir);
    return dir;
}

fs::path RuntimePaths::logDir() {
    fs::path dir = userDataDir() / "logs";
    fs::create_directories(dir);
    return dir;
}

fs::path RuntimePaths::defaultOutputDir() {
    fs::path dir = userDataDir() / "output";
    fs::create_directories(dir);
    return dir;
}

bool RuntimePaths::isWritableDirectory(const fs::path& dir) {
    std::error_code error;
    fs::create_directories(dir, error);
    if (error || !fs::exists(dir, error) || !fs::is_directory(dir, error)) {
        return false;
    }

    const fs::path probe = dir / ".write_test";
    {
        std::ofstream out(probe, std::ios::binary | std::ios::trunc);
        if (!out) {
            return false;
        }
        out << "ok";
        if (!out) {
            return false;
        }
    }
    fs::remove(probe, error);
    return !fs::exists(probe, error);
}

std::string RuntimePaths::version() {
    std::ifstream in(appDir() / "VERSION.txt");
    std::string value;
    std::getline(in, value);
    return value.empty() ? "1.0.0" : value;
}
