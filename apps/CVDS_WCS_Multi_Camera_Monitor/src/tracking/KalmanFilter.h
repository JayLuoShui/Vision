#pragma once

#include <opencv2/core.hpp>

class KalmanFilter {
public:
    void initiate(const cv::Rect2f& box) { state_ = box; }
    cv::Rect2f predict() const { return state_; }
    cv::Rect2f update(const cv::Rect2f& box) { state_ = box; return state_; }

private:
    cv::Rect2f state_;
};
