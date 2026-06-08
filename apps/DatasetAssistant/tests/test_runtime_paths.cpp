#include "core/RuntimePaths.h"

#include <cassert>
#include <filesystem>
#include <iostream>

namespace fs = std::filesystem;

int main() {
    const fs::path root = fs::temp_directory_path() / "dataset_assistant_runtime_paths_test";
    fs::remove_all(root);

    assert(RuntimePaths::isWritableDirectory(root));
    assert(fs::exists(root));

    const fs::path probe = root / ".write_test";
    assert(!fs::exists(probe));

    fs::remove_all(root);
    std::cout << "test_runtime_paths passed\n";
    return 0;
}
