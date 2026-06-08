#pragma once

#include <opencv2/core.hpp>

#include <filesystem>
#include <string>
#include <vector>

struct Point2D {
    double x = 0.0;
    double y = 0.0;
};

struct BBox {
    double x1 = 0.0;
    double y1 = 0.0;
    double x2 = 0.0;
    double y2 = 0.0;
};

struct RectI {
    int x = 0;
    int y = 0;
    int width = 0;
    int height = 0;
};

struct Polygon {
    std::vector<Point2D> points;
};

struct AnnotationObject {
    int classId = -1;
    std::string className;
    BBox box;
    std::vector<Polygon> polygons;
    cv::Mat mask;
    double confidence = 0.0;
    bool hasMask = false;
    bool hasPolygon = false;
};

struct ImageAnnotation {
    std::filesystem::path imagePath;
    int width = 0;
    int height = 0;
    std::vector<AnnotationObject> objects;
};

struct DetectionResult {
    int classId = -1;
    std::string className;
    BBox box;
    double confidence = 0.0;
    cv::Mat mask;
    bool hasMask = false;
};
