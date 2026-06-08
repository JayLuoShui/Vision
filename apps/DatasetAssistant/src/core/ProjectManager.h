#pragma once

#include "model/ProjectConfig.h"

#include <filesystem>

class ProjectManager {
public:
    static ProjectConfig createDefault(const std::filesystem::path& projectFile);
    static bool save(const ProjectConfig& config, const std::filesystem::path& path);
    static ProjectConfig load(const std::filesystem::path& path);
};
