#include "utils/Geometry.h"

#include <algorithm>
#include <cmath>

namespace Geometry {

std::vector<cv::Point> toCvPolygon(const QVector<QPoint>& polygon) {
    std::vector<cv::Point> out;
    out.reserve(static_cast<size_t>(polygon.size()));
    for (const QPoint& point : polygon) {
        out.emplace_back(point.x(), point.y());
    }
    return out;
}

bool pointInPolygon(const cv::Point2f& point, const QVector<QPoint>& polygon) {
    return pointInPolygon(point, toCvPolygon(polygon));
}

bool pointInPolygon(const cv::Point2f& point, const std::vector<cv::Point>& polygon) {
    if (polygon.size() < 3) {
        return false;
    }
    return cv::pointPolygonTest(polygon, point, false) >= 0.0;
}

cv::Point2f boxCenter(const cv::Rect2f& box) {
    return {box.x + box.width * 0.5f, box.y + box.height * 0.5f};
}

cv::Rect2f clampRect(const cv::Rect2f& rect, int width, int height) {
    const float x1 = std::clamp(rect.x, 0.0f, static_cast<float>(std::max(0, width - 1)));
    const float y1 = std::clamp(rect.y, 0.0f, static_cast<float>(std::max(0, height - 1)));
    const float x2 = std::clamp(rect.x + rect.width, 0.0f, static_cast<float>(std::max(0, width - 1)));
    const float y2 = std::clamp(rect.y + rect.height, 0.0f, static_cast<float>(std::max(0, height - 1)));
    return {x1, y1, std::max(0.0f, x2 - x1), std::max(0.0f, y2 - y1)};
}

double distance(const cv::Point2f& a, const cv::Point2f& b) {
    const double dx = static_cast<double>(a.x - b.x);
    const double dy = static_cast<double>(a.y - b.y);
    return std::sqrt(dx * dx + dy * dy);
}

}  // namespace Geometry
