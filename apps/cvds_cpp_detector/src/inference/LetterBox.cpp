#include "inference/LetterBox.h"

#include <algorithm>
#include <cmath>

#include <opencv2/imgproc.hpp>

cv::Mat letterboxImage(const cv::Mat& image, int targetWidth, int targetHeight, LetterBoxInfo* info) {
    if (image.empty() || targetWidth <= 0 || targetHeight <= 0) {
        if (info) *info = {};
        return {};
    }

    LetterBoxInfo meta;
    meta.originalWidth = image.cols;
    meta.originalHeight = image.rows;
    meta.inputWidth = targetWidth;
    meta.inputHeight = targetHeight;
    meta.scale = std::min(
        targetWidth / static_cast<float>(image.cols),
        targetHeight / static_cast<float>(image.rows));
    const int resizedWidth = std::clamp(
        static_cast<int>(std::round(image.cols * meta.scale)), 1, targetWidth);
    const int resizedHeight = std::clamp(
        static_cast<int>(std::round(image.rows * meta.scale)), 1, targetHeight);
    const int left = (targetWidth - resizedWidth) / 2;
    const int top = (targetHeight - resizedHeight) / 2;
    meta.padX = static_cast<float>(left);
    meta.padY = static_cast<float>(top);

    cv::Mat resized;
    cv::resize(image, resized, cv::Size(resizedWidth, resizedHeight), 0.0, 0.0, cv::INTER_LINEAR);
    cv::Mat canvas(targetHeight, targetWidth, image.type(), cv::Scalar(114, 114, 114));
    resized.copyTo(canvas(cv::Rect(left, top, resizedWidth, resizedHeight)));
    if (info) *info = meta;
    return canvas;
}

cv::Rect2f mapBoxToOriginal(const cv::Rect2f& box, const LetterBoxInfo& info) {
    if (info.originalWidth <= 0 || info.originalHeight <= 0) return {};

    const float scale = std::max(1e-6f, info.scale);
    const float x1 = (box.x - info.padX) / scale;
    const float y1 = (box.y - info.padY) / scale;
    const float x2 = (box.x + box.width - info.padX) / scale;
    const float y2 = (box.y + box.height - info.padY) / scale;
    const float ox1 = std::clamp(x1, 0.0f, static_cast<float>(info.originalWidth));
    const float oy1 = std::clamp(y1, 0.0f, static_cast<float>(info.originalHeight));
    const float ox2 = std::clamp(x2, 0.0f, static_cast<float>(info.originalWidth));
    const float oy2 = std::clamp(y2, 0.0f, static_cast<float>(info.originalHeight));
    return {ox1, oy1, std::max(0.0f, ox2 - ox1), std::max(0.0f, oy2 - oy1)};
}
