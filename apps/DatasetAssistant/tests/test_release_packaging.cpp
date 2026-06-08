#include <cassert>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

namespace {

std::string readText(const fs::path& path) {
    std::ifstream in(path);
    assert(in && "file must be readable");
    std::ostringstream buffer;
    buffer << in.rdbuf();
    return buffer.str();
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
    const fs::path script = repoRoot() / "apps" / "DatasetAssistant" / "packaging" / "build_release.ps1";
    const std::string text = readText(script);

    assert(text.find("New-SelfSignedCertificate") != std::string::npos);
    assert(text.find("signtool.exe") != std::string::npos);
    assert(text.find("DatasetAssistant.exe") != std::string::npos);
    assert(text.find("DatasetAssistant_Setup_") != std::string::npos);
    return 0;
}
