#pragma once

#include "model/DatasetConfig.h"

#include <filesystem>
#include <vector>

struct DatasetItem {
    std::filesystem::path imagePath;
    std::filesystem::path annotationPath;
    bool hasAnnotation = false;
};

struct SplitResult {
    std::vector<DatasetItem> train;
    std::vector<DatasetItem> val;
    std::vector<DatasetItem> test;
};

class DatasetSplitter {
public:
    static SplitResult splitFiles(const std::filesystem::path& imageDir, const std::filesystem::path& labelDir, const SplitConfig& config);
    static void exportDataset(const SplitResult& split, const std::filesystem::path& outputDir, const SplitConfig& config);
    static void exportYolo(const SplitResult& split, const std::filesystem::path& outputDir, const SplitConfig& config);
    static void exportVoc(const SplitResult& split, const std::filesystem::path& outputDir, const SplitConfig& config);
    static void exportCoco(const SplitResult& split, const std::filesystem::path& outputDir, const SplitConfig& config);
    static void exportMaskPng(const SplitResult& split, const std::filesystem::path& outputDir, const SplitConfig& config);
};
