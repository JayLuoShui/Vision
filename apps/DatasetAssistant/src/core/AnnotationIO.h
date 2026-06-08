#pragma once

#include "model/Annotation.h"

#include <filesystem>
#include <string>
#include <vector>

class AnnotationIO {
public:
    static ImageAnnotation loadYolo(
        const std::filesystem::path& labelPath,
        const std::filesystem::path& imagePath,
        int width,
        int height,
        const std::vector<std::string>& classNames
    );
    static void saveYolo(const ImageAnnotation& annotation, const std::filesystem::path& labelPath, const std::vector<std::string>& classNames, bool preferSegment);
    static ImageAnnotation loadVoc(const std::filesystem::path& xmlPath, const std::vector<std::string>& classNames);
    static void saveVoc(const ImageAnnotation& annotation, const std::filesystem::path& xmlPath);
    static std::vector<ImageAnnotation> loadCoco(const std::filesystem::path& jsonPath, const std::vector<std::string>& classNames);
    static void saveCoco(const std::vector<ImageAnnotation>& annotations, const std::filesystem::path& jsonPath, const std::vector<std::string>& classNames);
    static cv::Mat loadMaskPng(const std::filesystem::path& maskPath);
    static void saveMaskPng(const cv::Mat& mask, const std::filesystem::path& maskPath, const std::filesystem::path& sidecarPath, const std::vector<std::string>& classNames);
};
