#pragma once

#include <opencv2/core.hpp>

class KalmanFilter {
public:
    void initiate(const cv::Rect2f& box);
    cv::Rect2f predict(double dtSeconds);
    cv::Rect2f update(const cv::Rect2f& measurement, double dtSeconds);
    bool initialized() const { return initialized_; }

private:
    static cv::Vec4f boxToMeasurement(const cv::Rect2f& box);
    static cv::Rect2f measurementToBox(const cv::Vec4f& value);

    cv::Vec4f position_{0.0f, 0.0f, 0.0f, 0.0f};
    cv::Vec4f velocity_{0.0f, 0.0f, 0.0f, 0.0f};
    cv::Vec4f positionVariance_{10.0f, 10.0f, 10.0f, 10.0f};
    cv::Vec4f velocityVariance_{100.0f, 100.0f, 100.0f, 100.0f};
    bool initialized_ = false;
};
