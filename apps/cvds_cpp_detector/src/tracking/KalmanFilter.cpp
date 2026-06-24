#include "tracking/KalmanFilter.h"

#include <algorithm>
#include <cmath>

namespace {
constexpr float kProcessPositionNoise = 1.0f;
constexpr float kProcessVelocityNoise = 4.0f;
constexpr float kMeasurementNoise = 4.0f;
}

cv::Vec4f KalmanFilter::boxToMeasurement(const cv::Rect2f& box) {
    return {
        box.x + box.width * 0.5f,
        box.y + box.height * 0.5f,
        std::max(1.0f, box.width),
        std::max(1.0f, box.height)};
}

cv::Rect2f KalmanFilter::measurementToBox(const cv::Vec4f& value) {
    const float width = std::max(1.0f, value[2]);
    const float height = std::max(1.0f, value[3]);
    return {value[0] - width * 0.5f, value[1] - height * 0.5f, width, height};
}

void KalmanFilter::initiate(const cv::Rect2f& box) {
    position_ = boxToMeasurement(box);
    velocity_ = cv::Vec4f(0.0f, 0.0f, 0.0f, 0.0f);
    positionVariance_ = cv::Vec4f(10.0f, 10.0f, 10.0f, 10.0f);
    velocityVariance_ = cv::Vec4f(100.0f, 100.0f, 100.0f, 100.0f);
    initialized_ = true;
}

cv::Rect2f KalmanFilter::predict(double dtSeconds) {
    if (!initialized_) return {};

    const float dt = static_cast<float>(std::clamp(dtSeconds, 1e-3, 1.0));
    for (int i = 0; i < 4; ++i) {
        position_[i] += velocity_[i] * dt;
        positionVariance_[i] += dt * dt * velocityVariance_[i] + kProcessPositionNoise;
        velocityVariance_[i] += kProcessVelocityNoise;
    }
    return measurementToBox(position_);
}

cv::Rect2f KalmanFilter::update(const cv::Rect2f& measurement, double dtSeconds) {
    if (!initialized_) {
        initiate(measurement);
        return measurement;
    }

    const float dt = static_cast<float>(std::clamp(dtSeconds, 1e-3, 1.0));
    const cv::Vec4f observed = boxToMeasurement(measurement);
    for (int i = 0; i < 4; ++i) {
        const float innovation = observed[i] - position_[i];
        const float gain = positionVariance_[i] / (positionVariance_[i] + kMeasurementNoise);
        position_[i] += gain * innovation;
        positionVariance_[i] = std::max(1e-3f, (1.0f - gain) * positionVariance_[i]);

        const float velocityGain = velocityVariance_[i] /
            (velocityVariance_[i] + kMeasurementNoise / (dt * dt));
        velocity_[i] += velocityGain * (innovation / dt);
        velocityVariance_[i] = std::max(1e-3f, (1.0f - velocityGain) * velocityVariance_[i]);
    }
    return measurementToBox(position_);
}
