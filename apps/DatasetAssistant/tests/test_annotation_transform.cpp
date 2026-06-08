#include "core/AnnotationTransform.h"

#include <opencv2/core.hpp>

#include <cassert>
#include <cmath>
#include <iostream>

namespace {

bool near(double a, double b, double eps = 1e-6) {
    return std::abs(a - b) <= eps;
}

ImageAnnotation sampleAnnotation() {
    ImageAnnotation ann;
    ann.imagePath = "sample.jpg";
    ann.width = 100;
    ann.height = 50;
    AnnotationObject obj;
    obj.classId = 1;
    obj.className = "parcel";
    obj.box = {10, 10, 40, 30};
    obj.polygons.push_back({{{10, 10}, {40, 10}, {40, 30}, {10, 30}}});
    obj.hasPolygon = true;
    obj.mask = cv::Mat::zeros(50, 100, CV_8UC1);
    obj.mask(cv::Rect(10, 10, 30, 20)).setTo(255);
    obj.hasMask = true;
    ann.objects.push_back(obj);
    return ann;
}

void testResize() {
    cv::Mat image = cv::Mat::zeros(50, 100, CV_8UC3);
    ImageAnnotation ann = sampleAnnotation();
    TransformResult result = AnnotationTransform::resize(image, ann, 200, 100);
    assert(result.image.cols == 200 && result.image.rows == 100);
    const auto& obj = result.annotation.objects.at(0);
    assert(near(obj.box.x1, 20));
    assert(near(obj.box.y1, 20));
    assert(near(obj.box.x2, 80));
    assert(near(obj.box.y2, 60));
    assert(near(obj.polygons.at(0).points.at(2).x, 80));
    assert(obj.mask.cols == 200 && obj.mask.rows == 100);
    assert(obj.mask.at<uchar>(25, 25) == 255);
}

void testLetterbox() {
    cv::Mat image = cv::Mat::zeros(50, 100, CV_8UC3);
    ImageAnnotation ann = sampleAnnotation();
    TransformResult result = AnnotationTransform::letterbox(image, ann, 200, 200, cv::Scalar(114, 114, 114));
    assert(result.image.cols == 200 && result.image.rows == 200);
    const auto& box = result.annotation.objects.at(0).box;
    assert(near(box.x1, 20));
    assert(near(box.y1, 70));
    assert(near(box.x2, 80));
    assert(near(box.y2, 110));
}

void testCropAndDropSmall() {
    cv::Mat image = cv::Mat::zeros(50, 100, CV_8UC3);
    ImageAnnotation ann = sampleAnnotation();
    TransformResult kept = AnnotationTransform::crop(image, ann, {20, 0, 50, 40}, 0.2);
    assert(kept.image.cols == 50 && kept.image.rows == 40);
    assert(kept.annotation.objects.size() == 1);
    const auto& box = kept.annotation.objects.at(0).box;
    assert(near(box.x1, 0));
    assert(near(box.y1, 10));
    assert(near(box.x2, 20));
    assert(near(box.y2, 30));

    TransformResult dropped = AnnotationTransform::crop(image, ann, {39, 0, 20, 40}, 0.2);
    assert(dropped.annotation.objects.empty());
}

void testPolygonCropClipsEdges() {
    cv::Mat image = cv::Mat::zeros(80, 80, CV_8UC3);
    ImageAnnotation ann;
    ann.width = 80;
    ann.height = 80;
    AnnotationObject obj;
    obj.classId = 0;
    obj.className = "parcel";
    obj.box = {-10, -10, 70, 70};
    obj.polygons.push_back({{{30, -10}, {70, 30}, {30, 70}, {-10, 30}}});
    obj.hasPolygon = true;
    ann.objects.push_back(obj);

    TransformResult cropped = AnnotationTransform::crop(image, ann, {0, 0, 60, 60}, 0.1);
    assert(cropped.annotation.objects.size() == 1);
    const auto& polygon = cropped.annotation.objects.at(0).polygons.at(0);
    assert(polygon.points.size() >= 8);
    bool hasRightTopIntersection = false;
    bool hasBottomRightIntersection = false;
    for (const auto& point : polygon.points) {
        assert(point.x >= -1e-6 && point.x <= 60 + 1e-6);
        assert(point.y >= -1e-6 && point.y <= 60 + 1e-6);
        if (near(point.x, 60) && near(point.y, 20)) {
            hasRightTopIntersection = true;
        }
        if (near(point.x, 40) && near(point.y, 60)) {
            hasBottomRightIntersection = true;
        }
    }
    assert(hasRightTopIntersection);
    assert(hasBottomRightIntersection);
}

void testTilingCrossBoundary() {
    cv::Mat image = cv::Mat::zeros(50, 100, CV_8UC3);
    ImageAnnotation ann = sampleAnnotation();
    auto tiles = AnnotationTransform::tile(image, ann, 30, 30, 0, 0, false, 0.2);
    assert(tiles.size() == 3);
    assert(tiles.at(0).annotation.objects.size() == 1);
    assert(tiles.at(1).annotation.objects.size() == 1);
    assert(near(tiles.at(1).annotation.objects.at(0).box.x1, 0));
    assert(near(tiles.at(1).annotation.objects.at(0).box.x2, 10));
}

void testFlip() {
    cv::Mat image = cv::Mat::zeros(50, 100, CV_8UC3);
    ImageAnnotation ann = sampleAnnotation();
    auto h = AnnotationTransform::flipHorizontal(image, ann);
    assert(near(h.annotation.objects.at(0).box.x1, 60));
    assert(near(h.annotation.objects.at(0).box.x2, 90));
    auto v = AnnotationTransform::flipVertical(image, ann);
    assert(near(v.annotation.objects.at(0).box.y1, 20));
    assert(near(v.annotation.objects.at(0).box.y2, 40));
}

void testRotate() {
    cv::Mat image = cv::Mat::zeros(50, 100, CV_8UC3);
    ImageAnnotation ann = sampleAnnotation();
    auto r90 = AnnotationTransform::rotate90(image, ann);
    assert(r90.image.cols == 50 && r90.image.rows == 100);
    assert(near(r90.annotation.objects.at(0).box.x1, 20));
    assert(near(r90.annotation.objects.at(0).box.y1, 10));
    assert(near(r90.annotation.objects.at(0).box.x2, 40));
    assert(near(r90.annotation.objects.at(0).box.y2, 40));

    auto r180 = AnnotationTransform::rotate180(image, ann);
    assert(near(r180.annotation.objects.at(0).box.x1, 60));
    assert(near(r180.annotation.objects.at(0).box.y1, 20));
    auto r270 = AnnotationTransform::rotate270(image, ann);
    assert(r270.image.cols == 50 && r270.image.rows == 100);
    assert(near(r270.annotation.objects.at(0).box.x1, 10));
    assert(near(r270.annotation.objects.at(0).box.y1, 60));
}

void testEmptyAnnotation() {
    cv::Mat image = cv::Mat::zeros(20, 20, CV_8UC3);
    ImageAnnotation ann;
    ann.width = 20;
    ann.height = 20;
    auto result = AnnotationTransform::resize(image, ann, 10, 10);
    assert(result.annotation.objects.empty());
    assert(result.annotation.width == 10 && result.annotation.height == 10);
}

}  // namespace

int main() {
    testResize();
    testLetterbox();
    testCropAndDropSmall();
    testPolygonCropClipsEdges();
    testTilingCrossBoundary();
    testFlip();
    testRotate();
    testEmptyAnnotation();
    std::cout << "test_annotation_transform passed\n";
    return 0;
}
