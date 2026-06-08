#include "core/ImageProcessor.h"

#include <opencv2/imgproc.hpp>

cv::Mat ImageProcessor::resizeFixed(const cv::Mat& image, int width, int height) {
    cv::Mat out;
    cv::resize(image, out, cv::Size(width, height), 0, 0, cv::INTER_LINEAR);
    return out;
}

cv::Mat ImageProcessor::letterbox(const cv::Mat& image, int width, int height, const cv::Scalar& color) {
    const double scale = std::min(static_cast<double>(width) / image.cols, static_cast<double>(height) / image.rows);
    cv::Mat resized;
    cv::resize(image, resized, cv::Size(static_cast<int>(image.cols * scale), static_cast<int>(image.rows * scale)));
    cv::Mat out(height, width, image.type(), color);
    resized.copyTo(out(cv::Rect((width - resized.cols) / 2, (height - resized.rows) / 2, resized.cols, resized.rows)));
    return out;
}

cv::Mat ImageProcessor::adjustBrightnessContrast(const cv::Mat& image, double brightness, double contrast) {
    cv::Mat out;
    image.convertTo(out, -1, contrast, brightness);
    return out;
}
