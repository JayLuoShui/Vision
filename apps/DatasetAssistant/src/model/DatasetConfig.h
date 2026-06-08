#pragma once

#include <cstdint>
#include <string>
#include <vector>

enum class AnnotationFormat {
    Yolo,
    Coco,
    Voc,
    MaskPng
};

enum class DatasetFormat {
    Yolo,
    Coco,
    Voc,
    MaskPng
};

struct SplitConfig {
    double trainRatio = 0.7;
    double valRatio = 0.2;
    double testRatio = 0.1;
    std::uint32_t seed = 20260528;
    bool includeNegative = true;
    DatasetFormat format = DatasetFormat::Yolo;
    AnnotationFormat sourceAnnotationFormat = AnnotationFormat::Yolo;
    std::vector<std::string> classNames;
};
