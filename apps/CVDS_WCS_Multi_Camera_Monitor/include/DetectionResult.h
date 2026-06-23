#pragma once

#include <QRectF>
#include <QString>

struct DetectionResult {
    QString cameraId;
    int trackId = -1;
    int classId = -1;
    QString className;
    double confidence = 0.0;
    QRectF box;
};
