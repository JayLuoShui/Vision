#pragma once

#include <opencv2/core.hpp>

struct LetterBoxInfo {
    float scale = 1.0f;
    int padX = 0;
    int padY = 0;
    int inputWidth = 0;
    int inputHeight = 0;
    int originalWidth = 0;
    int originalHeight = 0;
};

cv::Mat letterboxImage(const cv::Mat& image, int targetWidth, int targetHeight, LetterBoxInfo* info);
cv::Rect2f mapBoxToOriginal(const cv::Rect2f& box, const LetterBoxInfo& info);
