#pragma once

#include <QPoint>
#include <QVector>
#include <opencv2/core.hpp>

#include <vector>

namespace Geometry {

std::vector<cv::Point> toCvPolygon(const QVector<QPoint>& polygon);
bool pointInPolygon(const cv::Point2f& point, const QVector<QPoint>& polygon);
bool pointInPolygon(const cv::Point2f& point, const std::vector<cv::Point>& polygon);
cv::Point2f boxCenter(const cv::Rect2f& box);
cv::Rect2f clampRect(const cv::Rect2f& rect, int width, int height);
double distance(const cv::Point2f& a, const cv::Point2f& b);

}  // namespace Geometry
