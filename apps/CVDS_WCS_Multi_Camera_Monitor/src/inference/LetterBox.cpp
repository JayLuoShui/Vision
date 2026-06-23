#include "inference/LetterBox.h"
#include <opencv2/imgproc.hpp>
#include <algorithm>

cv::Mat letterboxImage(const cv::Mat& image, int targetWidth, int targetHeight, LetterBoxInfo* info) {
    LetterBoxInfo meta;
    meta.originalWidth = image.cols;
    meta.originalHeight = image.rows;
    meta.inputWidth = targetWidth;
    meta.inputHeight = targetHeight;
    meta.scale = std::min(targetWidth / static_cast<float>(std::max(1, image.cols)), targetHeight / static_cast<float>(std::max(1, image.rows)));
    const int rw = std::max(1, static_cast<int>(image.cols * meta.scale));
    const int rh = std::max(1, static_cast<int>(image.rows * meta.scale));
    meta.padX = (targetWidth - rw) / 2;
    meta.padY = (targetHeight - rh) / 2;
    cv::Mat resized;
    cv::resize(image, resized, cv::Size(rw, rh));
    cv::Mat canvas(targetHeight, targetWidth, image.type(), cv::Scalar(114, 114, 114));
    resized.copyTo(canvas(cv::Rect(meta.padX, meta.padY, rw, rh)));
    if (info) *info = meta;
    return canvas;
}

cv::Rect2f mapBoxToOriginal(const cv::Rect2f& box, const LetterBoxInfo& info) {
    const float scale = std::max(1e-6f, info.scale);
    const float x1 = (box.x - info.padX) / scale;
    const float y1 = (box.y - info.padY) / scale;
    const float x2 = (box.x + box.width - info.padX) / scale;
    const float y2 = (box.y + box.height - info.padY) / scale;
    const float ox1 = std::clamp(x1, 0.0f, static_cast<float>(std::max(0, info.originalWidth - 1)));
    const float oy1 = std::clamp(y1, 0.0f, static_cast<float>(std::max(0, info.originalHeight - 1)));
    const float ox2 = std::clamp(x2, 0.0f, static_cast<float>(std::max(0, info.originalWidth - 1)));
    const float oy2 = std::clamp(y2, 0.0f, static_cast<float>(std::max(0, info.originalHeight - 1)));
    return {ox1, oy1, std::max(0.0f, ox2 - ox1), std::max(0.0f, oy2 - oy1)};
}
