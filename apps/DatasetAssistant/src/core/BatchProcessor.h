#pragma once

#include "model/ProjectConfig.h"

#include <filesystem>
#include <string>
#include <vector>

struct BatchProcessSummary {
    int processedImages = 0;
    int skippedImages = 0;
    int failedItems = 0;
    std::vector<std::string> errors;
};

class BatchProcessor {
public:
    static BatchProcessSummary processImages(const ProjectConfig& config);
};
