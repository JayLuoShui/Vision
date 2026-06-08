#include "core/AnnotationTransform.h"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

namespace {

ImageAnnotation sampleAnnotation() {
    ImageAnnotation ann;
    ann.imagePath = "visual_sample.jpg";
    ann.width = 220;
    ann.height = 140;

    AnnotationObject boxObject;
    boxObject.classId = 0;
    boxObject.className = "box";
    boxObject.box = {35, 35, 125, 95};
    boxObject.polygons.push_back({{{35, 45}, {110, 35}, {125, 80}, {70, 95}}});
    boxObject.hasPolygon = true;
    boxObject.mask = cv::Mat::zeros(140, 220, CV_8UC1);
    std::vector<cv::Point> points{{35, 45}, {110, 35}, {125, 80}, {70, 95}};
    cv::fillPoly(boxObject.mask, std::vector<std::vector<cv::Point>>{points}, cv::Scalar(255));
    boxObject.hasMask = true;
    ann.objects.push_back(boxObject);

    AnnotationObject crossObject;
    crossObject.classId = 1;
    crossObject.className = "cross_tile";
    crossObject.box = {145, 50, 210, 120};
    crossObject.polygons.push_back({{{145, 65}, {205, 50}, {210, 110}, {160, 120}}});
    crossObject.hasPolygon = true;
    ann.objects.push_back(crossObject);
    return ann;
}

cv::Mat sampleImage() {
    cv::Mat image(140, 220, CV_8UC3, cv::Scalar(38, 44, 50));
    cv::rectangle(image, cv::Rect(0, 95, 220, 45), cv::Scalar(70, 72, 68), cv::FILLED);
    cv::rectangle(image, cv::Rect(35, 35, 90, 60), cv::Scalar(54, 122, 180), cv::FILLED);
    cv::rectangle(image, cv::Rect(145, 50, 65, 70), cv::Scalar(180, 118, 54), cv::FILLED);
    cv::line(image, {0, 96}, {220, 96}, cv::Scalar(120, 120, 120), 2);
    return image;
}

void drawAnnotation(cv::Mat& image, const ImageAnnotation& ann, const std::string& title) {
    const cv::Scalar boxColor(0, 255, 255);
    const cv::Scalar polygonColor(0, 180, 255);
    const cv::Scalar maskColor(90, 220, 90);
    for (const auto& object : ann.objects) {
        if (object.hasMask && !object.mask.empty()) {
            cv::Mat resizedMask;
            if (object.mask.size() == image.size()) {
                resizedMask = object.mask;
            } else {
                cv::resize(object.mask, resizedMask, image.size(), 0, 0, cv::INTER_NEAREST);
            }
            cv::Mat overlay(image.size(), image.type(), maskColor);
            overlay.copyTo(image, resizedMask > 0);
            cv::addWeighted(image, 0.75, overlay, 0.25, 0.0, image);
        }
        cv::rectangle(
            image,
            cv::Rect(
                static_cast<int>(std::round(object.box.x1)),
                static_cast<int>(std::round(object.box.y1)),
                static_cast<int>(std::round(object.box.x2 - object.box.x1)),
                static_cast<int>(std::round(object.box.y2 - object.box.y1))
            ),
            boxColor,
            2
        );
        for (const auto& polygon : object.polygons) {
            std::vector<cv::Point> pts;
            for (const auto& point : polygon.points) {
                pts.emplace_back(static_cast<int>(std::round(point.x)), static_cast<int>(std::round(point.y)));
            }
            if (pts.size() >= 2) {
                cv::polylines(image, std::vector<std::vector<cv::Point>>{pts}, true, polygonColor, 2);
            }
        }
    }
    cv::putText(image, title, {8, 22}, cv::FONT_HERSHEY_SIMPLEX, 0.6, cv::Scalar(240, 240, 240), 2);
}

void saveVisual(const fs::path& outputDir, const std::string& name, TransformResult result) {
    cv::Mat visual = result.image.clone();
    drawAnnotation(visual, result.annotation, name);
    if (!cv::imwrite((outputDir / (name + ".png")).string(), visual)) {
        throw std::runtime_error("failed to write " + (outputDir / (name + ".png")).string());
    }
}

} // namespace

int main(int argc, char** argv) {
    const fs::path outputDir = argc > 1
        ? fs::u8path(argv[1])
        : fs::current_path() / "annotation_transform_visual";
    fs::create_directories(outputDir);

    cv::Mat image = sampleImage();
    ImageAnnotation ann = sampleAnnotation();
    saveVisual(outputDir, "00_original", {image, ann});
    saveVisual(outputDir, "01_resize", AnnotationTransform::resize(image, ann, 330, 210));
    saveVisual(outputDir, "02_letterbox", AnnotationTransform::letterbox(image, ann, 260, 260, cv::Scalar(114, 114, 114)));
    saveVisual(outputDir, "03_crop", AnnotationTransform::crop(image, ann, {55, 25, 135, 90}, 0.2));
    saveVisual(outputDir, "04_flip_horizontal", AnnotationTransform::flipHorizontal(image, ann));
    saveVisual(outputDir, "05_flip_vertical", AnnotationTransform::flipVertical(image, ann));
    saveVisual(outputDir, "06_rotate90", AnnotationTransform::rotate90(image, ann));
    saveVisual(outputDir, "07_rotate180", AnnotationTransform::rotate180(image, ann));
    saveVisual(outputDir, "08_rotate270", AnnotationTransform::rotate270(image, ann));

    const auto tiles = AnnotationTransform::tile(image, ann, 110, 80, 20, 20, true, 0.2);
    for (size_t i = 0; i < tiles.size(); ++i) {
        saveVisual(outputDir, "09_tile_" + std::to_string(i), tiles[i]);
    }

    std::cout << "annotation transform visuals written to: " << outputDir.u8string() << "\n";
    return 0;
}
