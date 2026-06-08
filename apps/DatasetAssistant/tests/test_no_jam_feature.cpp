#include <cassert>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

namespace {

std::string readText(const fs::path& path) {
    std::ifstream in(path);
    assert(in && "source file must be readable");
    std::ostringstream buffer;
    buffer << in.rdbuf();
    return buffer.str();
}

void assertNotContains(const std::string& text, const std::string& needle) {
    assert(text.find(needle) == std::string::npos);
}

fs::path repoRoot() {
    fs::path current = fs::current_path();
    for (int i = 0; i < 8; ++i) {
        if (fs::exists(current / "apps" / "DatasetAssistant" / "CMakeLists.txt")) {
            return current;
        }
        if (fs::exists(current / "DatasetAssistant" / "CMakeLists.txt")) {
            return current.parent_path();
        }
        current = current.parent_path();
    }
    return fs::current_path().parent_path().parent_path();
}

}  // namespace

int main() {
    const fs::path root = repoRoot();
    const fs::path appRoot = root / "apps" / "DatasetAssistant";

    const std::string cmake = readText(appRoot / "CMakeLists.txt");
    assertNotContains(cmake, "JamSynthesisPanel");
    assertNotContains(cmake, "JamSynthesizer");
    assertNotContains(cmake, "JamConfigIO");
    assertNotContains(cmake, "test_jam_synthesizer");

    const std::string mainWindow = readText(appRoot / "src" / "app" / "MainWindow.cpp");
    assertNotContains(mainWindow, "堵包合成");
    assertNotContains(mainWindow, "JamSynthesisPanel");

    const std::string main = readText(appRoot / "src" / "app" / "main.cpp");
    assertNotContains(main, "--jam-simulate");
    assertNotContains(main, "runJamSimulate");

    const std::string projectConfig = readText(appRoot / "src" / "model" / "ProjectConfig.h");
    assertNotContains(projectConfig, "JamConfig");

    const std::string projectManager = readText(appRoot / "src" / "core" / "ProjectManager.cpp");
    assertNotContains(projectManager, "jam_");

    return 0;
}
