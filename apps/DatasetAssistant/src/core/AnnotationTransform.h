#pragma once

#include "model/Annotation.h"

#include <opencv2/core.hpp>

#include <vector>

struct TransformResult {
    cv::Mat image;
    ImageAnnotation annotation;
};

class AnnotationTransform {
public:
    static TransformResult resize(const cv::Mat& image, const ImageAnnotation& annotation, int width, int height);
    static TransformResult letterbox(const cv::Mat& image, const ImageAnnotation& annotation, int width, int height, const cv::Scalar& color);
    static TransformResult crop(const cv::Mat& image, const ImageAnnotation& annotation, RectI rect, double keepVisibleRatio);
    static std::vector<TransformResult> tile(
        const cv::Mat& image,
        const ImageAnnotation& annotation,
        int tileWidth,
        int tileHeight,
        int overlapX,
        int overlapY,
        bool padEdges,
        double keepVisibleRatio
    );
    static TransformResult flipHorizontal(const cv::Mat& image, const ImageAnnotation& annotation);
    static TransformResult flipVertical(const cv::Mat& image, const ImageAnnotation& annotation);
    static TransformResult rotate90(const cv::Mat& image, const ImageAnnotation& annotation);
    static TransformResult rotate180(const cv::Mat& image, const ImageAnnotation& annotation);
    static TransformResult rotate270(const cv::Mat& image, const ImageAnnotation& annotation);
};
