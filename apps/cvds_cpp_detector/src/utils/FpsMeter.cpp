#include "utils/FpsMeter.h"

#include <algorithm>

void FpsMeter::reset() {
    frameCount_ = 0;
    currentFps_ = 0.0;
    timer_.restart();
}

double FpsMeter::addFrame() {
    if (!timer_.isValid()) {
        timer_.start();
    }
    ++frameCount_;
    const qint64 elapsedMs = timer_.elapsed();
    if (elapsedMs >= 1000) {
        currentFps_ = frameCount_ * 1000.0 / std::max<qint64>(1, elapsedMs);
        frameCount_ = 0;
        timer_.restart();
    }
    return currentFps_;
}

double FpsMeter::fps() const {
    return currentFps_;
}
