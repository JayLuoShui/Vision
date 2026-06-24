#pragma once

#include <QElapsedTimer>

class FpsMeter {
public:
    void reset();
    double addFrame();
    double fps() const;

private:
    QElapsedTimer timer_;
    int frameCount_ = 0;
    double currentFps_ = 0.0;
};
