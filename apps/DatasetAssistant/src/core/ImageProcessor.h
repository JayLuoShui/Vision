#pragma once

#include "model/Annotation.h"
#include "model/TransformConfig.h"

#include <opencv2/core.hpp>

class ImageProcessor {
public:
    static cv::Mat resizeFixed(const cv::Mat& image, int width, int height);
    static cv::Mat letterbox(const cv::Mat& image, int width, int height, const cv::Scalar& color);
    static cv::Mat adjustBrightnessContrast(const cv::Mat& image, double brightness, double contrast);
};
