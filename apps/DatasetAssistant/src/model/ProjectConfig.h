#pragma once

#include "model/DatasetConfig.h"
#include "model/InferenceConfig.h"
#include "model/TransformConfig.h"

#include <filesystem>
#include <string>
#include <vector>

struct ProjectConfig {
    std::filesystem::path projectFile;
    std::filesystem::path imageInputDir;
    std::filesystem::path videoInputPath;
    std::filesystem::path annotationDir;
    std::filesystem::path outputDir;
    AnnotationFormat annotationFormat = AnnotationFormat::Yolo;
    AnnotationFormat outputAnnotationFormat = AnnotationFormat::Yolo;
    std::vector<std::string> classNames;
    TransformConfig transform;
    SplitConfig split;
    InferenceConfig inference;
};
