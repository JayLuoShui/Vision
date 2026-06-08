#include "core/AnnotationTransform.h"

#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cmath>

namespace {

double area(const BBox& box) {
    return std::max(0.0, box.x2 - box.x1) * std::max(0.0, box.y2 - box.y1);
}

BBox intersectBox(const BBox& box, const RectI& rect) {
    return {
        std::max(box.x1, static_cast<double>(rect.x)),
        std::max(box.y1, static_cast<double>(rect.y)),
        std::min(box.x2, static_cast<double>(rect.x + rect.width)),
        std::min(box.y2, static_cast<double>(rect.y + rect.height))
    };
}

void recomputeBoxFromPolygon(AnnotationObject& object) {
    if (!object.hasPolygon || object.polygons.empty() || object.polygons.front().points.empty()) {
        return;
    }
    double minX = object.polygons.front().points.front().x;
    double minY = object.polygons.front().points.front().y;
    double maxX = minX;
    double maxY = minY;
    for (const auto& polygon : object.polygons) {
        for (const auto& point : polygon.points) {
            minX = std::min(minX, point.x);
            minY = std::min(minY, point.y);
            maxX = std::max(maxX, point.x);
            maxY = std::max(maxY, point.y);
        }
    }
    object.box = {minX, minY, maxX, maxY};
}

ImageAnnotation scaleAnnotation(const ImageAnnotation& annotation, double sx, double sy, int width, int height, double dx = 0, double dy = 0) {
    ImageAnnotation out = annotation;
    out.width = width;
    out.height = height;
    for (auto& object : out.objects) {
        object.box = {
            object.box.x1 * sx + dx,
            object.box.y1 * sy + dy,
            object.box.x2 * sx + dx,
            object.box.y2 * sy + dy
        };
        for (auto& polygon : object.polygons) {
            for (auto& point : polygon.points) {
                point.x = point.x * sx + dx;
                point.y = point.y * sy + dy;
            }
        }
        if (object.hasMask && !object.mask.empty()) {
            cv::Mat resized;
            cv::resize(object.mask, resized, cv::Size(std::max(1, static_cast<int>(std::round(annotation.width * sx))), std::max(1, static_cast<int>(std::round(annotation.height * sy)))), 0, 0, cv::INTER_NEAREST);
            if (dx != 0 || dy != 0 || resized.cols != width || resized.rows != height) {
                cv::Mat placed = cv::Mat::zeros(height, width, resized.type());
                cv::Rect roi(static_cast<int>(std::round(dx)), static_cast<int>(std::round(dy)), resized.cols, resized.rows);
                roi &= cv::Rect(0, 0, width, height);
                if (roi.width > 0 && roi.height > 0) {
                    resized(cv::Rect(0, 0, roi.width, roi.height)).copyTo(placed(roi));
                }
                object.mask = placed;
            } else {
                object.mask = resized;
            }
        }
    }
    return out;
}

enum class ClipEdge {
    Left,
    Right,
    Top,
    Bottom
};

bool insideEdge(const Point2D& point, const RectI& rect, ClipEdge edge) {
    switch (edge) {
        case ClipEdge::Left:
            return point.x >= rect.x;
        case ClipEdge::Right:
            return point.x <= rect.x + rect.width;
        case ClipEdge::Top:
            return point.y >= rect.y;
        case ClipEdge::Bottom:
            return point.y <= rect.y + rect.height;
    }
    return true;
}

Point2D edgeIntersection(const Point2D& from, const Point2D& to, const RectI& rect, ClipEdge edge) {
    const double dx = to.x - from.x;
    const double dy = to.y - from.y;
    double t = 0.0;
    if (edge == ClipEdge::Left) {
        t = (rect.x - from.x) / dx;
    } else if (edge == ClipEdge::Right) {
        t = (rect.x + rect.width - from.x) / dx;
    } else if (edge == ClipEdge::Top) {
        t = (rect.y - from.y) / dy;
    } else {
        t = (rect.y + rect.height - from.y) / dy;
    }
    return {from.x + t * dx, from.y + t * dy};
}

std::vector<Point2D> clipPointsToEdge(const std::vector<Point2D>& input, const RectI& rect, ClipEdge edge) {
    std::vector<Point2D> output;
    if (input.empty()) {
        return output;
    }
    Point2D previous = input.back();
    bool previousInside = insideEdge(previous, rect, edge);
    for (const auto& current : input) {
        const bool currentInside = insideEdge(current, rect, edge);
        if (currentInside) {
            if (!previousInside) {
                output.push_back(edgeIntersection(previous, current, rect, edge));
            }
            output.push_back(current);
        } else if (previousInside) {
            output.push_back(edgeIntersection(previous, current, rect, edge));
        }
        previous = current;
        previousInside = currentInside;
    }
    return output;
}

Polygon cropPolygonToRect(const Polygon& polygon, const RectI& rect) {
    std::vector<Point2D> clipped = polygon.points;
    clipped = clipPointsToEdge(clipped, rect, ClipEdge::Left);
    clipped = clipPointsToEdge(clipped, rect, ClipEdge::Right);
    clipped = clipPointsToEdge(clipped, rect, ClipEdge::Top);
    clipped = clipPointsToEdge(clipped, rect, ClipEdge::Bottom);
    Polygon out;
    for (const auto& point : clipped) {
        out.points.push_back({point.x - rect.x, point.y - rect.y});
    }
    return out;
}

AnnotationObject offsetObjectToCrop(const AnnotationObject& object, const RectI& rect, const BBox& clippedBox) {
    AnnotationObject out = object;
    out.box = {clippedBox.x1 - rect.x, clippedBox.y1 - rect.y, clippedBox.x2 - rect.x, clippedBox.y2 - rect.y};
    for (auto& polygon : out.polygons) {
        polygon = cropPolygonToRect(polygon, rect);
    }
    out.polygons.erase(
        std::remove_if(out.polygons.begin(), out.polygons.end(), [](const Polygon& polygon) {
            return polygon.points.size() < 3;
        }),
        out.polygons.end()
    );
    out.hasPolygon = !out.polygons.empty();
    if (out.hasPolygon) {
        recomputeBoxFromPolygon(out);
    }
    if (out.hasMask && !out.mask.empty()) {
        cv::Rect imageRect(0, 0, object.mask.cols, object.mask.rows);
        cv::Rect cropRect(rect.x, rect.y, rect.width, rect.height);
        cv::Rect valid = cropRect & imageRect;
        cv::Mat cropped = cv::Mat::zeros(rect.height, rect.width, out.mask.type());
        if (valid.width > 0 && valid.height > 0) {
            const cv::Rect sourceRoi = valid;
            const cv::Rect targetRoi(valid.x - cropRect.x, valid.y - cropRect.y, valid.width, valid.height);
            object.mask(sourceRoi).copyTo(cropped(targetRoi));
        }
        out.mask = cropped;
    }
    return out;
}

ImageAnnotation cropAnnotation(const ImageAnnotation& annotation, const RectI& rect, double keepVisibleRatio) {
    ImageAnnotation out;
    out.imagePath = annotation.imagePath;
    out.width = rect.width;
    out.height = rect.height;
    for (const auto& object : annotation.objects) {
        BBox clipped = intersectBox(object.box, rect);
        const double oldArea = area(object.box);
        const double newArea = area(clipped);
        if (oldArea <= 0 || newArea / oldArea < keepVisibleRatio) {
            continue;
        }
        out.objects.push_back(offsetObjectToCrop(object, rect, clipped));
    }
    return out;
}

void rotatePoint90(Point2D& point, int oldHeight) {
    const double x = point.x;
    point.x = oldHeight - point.y;
    point.y = x;
}

void rotatePoint180(Point2D& point, int oldWidth, int oldHeight) {
    point.x = oldWidth - point.x;
    point.y = oldHeight - point.y;
}

void rotatePoint270(Point2D& point, int oldWidth) {
    const double y = point.y;
    point.y = oldWidth - point.x;
    point.x = y;
}

template <typename Fn>
ImageAnnotation rotateAnnotation(const ImageAnnotation& annotation, int width, int height, Fn fn) {
    ImageAnnotation out = annotation;
    out.width = width;
    out.height = height;
    for (auto& object : out.objects) {
        Polygon corners{{{object.box.x1, object.box.y1}, {object.box.x2, object.box.y1}, {object.box.x2, object.box.y2}, {object.box.x1, object.box.y2}}};
        for (auto& point : corners.points) {
            fn(point);
        }
        object.polygons = object.hasPolygon ? object.polygons : std::vector<Polygon>{corners};
        for (auto& polygon : object.polygons) {
            for (auto& point : polygon.points) {
                fn(point);
            }
        }
        object.hasPolygon = true;
        recomputeBoxFromPolygon(object);
    }
    return out;
}

}  // namespace

TransformResult AnnotationTransform::resize(const cv::Mat& image, const ImageAnnotation& annotation, int width, int height) {
    TransformResult result;
    cv::resize(image, result.image, cv::Size(width, height), 0, 0, cv::INTER_LINEAR);
    result.annotation = scaleAnnotation(annotation, static_cast<double>(width) / image.cols, static_cast<double>(height) / image.rows, width, height);
    return result;
}

TransformResult AnnotationTransform::letterbox(const cv::Mat& image, const ImageAnnotation& annotation, int width, int height, const cv::Scalar& color) {
    const double scale = std::min(static_cast<double>(width) / image.cols, static_cast<double>(height) / image.rows);
    const int scaledW = static_cast<int>(std::round(image.cols * scale));
    const int scaledH = static_cast<int>(std::round(image.rows * scale));
    const int dx = (width - scaledW) / 2;
    const int dy = (height - scaledH) / 2;
    cv::Mat resized;
    cv::resize(image, resized, cv::Size(scaledW, scaledH), 0, 0, cv::INTER_LINEAR);
    TransformResult out;
    out.image = cv::Mat(height, width, image.type(), color);
    resized.copyTo(out.image(cv::Rect(dx, dy, scaledW, scaledH)));
    out.annotation = scaleAnnotation(annotation, scale, scale, width, height, dx, dy);
    return out;
}

TransformResult AnnotationTransform::crop(const cv::Mat& image, const ImageAnnotation& annotation, RectI rect, double keepVisibleRatio) {
    rect.x = std::clamp(rect.x, 0, image.cols);
    rect.y = std::clamp(rect.y, 0, image.rows);
    rect.width = std::min(rect.width, image.cols - rect.x);
    rect.height = std::min(rect.height, image.rows - rect.y);
    TransformResult out;
    out.image = image(cv::Rect(rect.x, rect.y, rect.width, rect.height)).clone();
    out.annotation = cropAnnotation(annotation, rect, keepVisibleRatio);
    return out;
}

std::vector<TransformResult> AnnotationTransform::tile(const cv::Mat& image, const ImageAnnotation& annotation, int tileWidth, int tileHeight, int overlapX, int overlapY, bool padEdges, double keepVisibleRatio) {
    std::vector<TransformResult> results;
    const int stepX = std::max(1, tileWidth - overlapX);
    const int stepY = std::max(1, tileHeight - overlapY);
    for (int y = 0; y < image.rows; y += stepY) {
        for (int x = 0; x < image.cols; x += stepX) {
            if (!padEdges && (x + tileWidth > image.cols || y + tileHeight > image.rows)) {
                continue;
            }
            RectI rect{x, y, std::min(tileWidth, image.cols - x), std::min(tileHeight, image.rows - y)};
            TransformResult tile = crop(image, annotation, rect, keepVisibleRatio);
            if (padEdges && (tile.image.cols != tileWidth || tile.image.rows != tileHeight)) {
                cv::Mat padded = cv::Mat::zeros(tileHeight, tileWidth, image.type());
                tile.image.copyTo(padded(cv::Rect(0, 0, tile.image.cols, tile.image.rows)));
                tile.image = padded;
                tile.annotation.width = tileWidth;
                tile.annotation.height = tileHeight;
            }
            results.push_back(tile);
        }
    }
    return results;
}

TransformResult AnnotationTransform::flipHorizontal(const cv::Mat& image, const ImageAnnotation& annotation) {
    TransformResult out;
    cv::flip(image, out.image, 1);
    out.annotation = annotation;
    for (auto& object : out.annotation.objects) {
        const double oldX1 = object.box.x1;
        object.box.x1 = image.cols - object.box.x2;
        object.box.x2 = image.cols - oldX1;
        for (auto& polygon : object.polygons) {
            for (auto& point : polygon.points) {
                point.x = image.cols - point.x;
            }
        }
        if (object.hasMask && !object.mask.empty()) {
            cv::flip(object.mask, object.mask, 1);
        }
    }
    return out;
}

TransformResult AnnotationTransform::flipVertical(const cv::Mat& image, const ImageAnnotation& annotation) {
    TransformResult out;
    cv::flip(image, out.image, 0);
    out.annotation = annotation;
    for (auto& object : out.annotation.objects) {
        const double oldY1 = object.box.y1;
        object.box.y1 = image.rows - object.box.y2;
        object.box.y2 = image.rows - oldY1;
        for (auto& polygon : object.polygons) {
            for (auto& point : polygon.points) {
                point.y = image.rows - point.y;
            }
        }
        if (object.hasMask && !object.mask.empty()) {
            cv::flip(object.mask, object.mask, 0);
        }
    }
    return out;
}

TransformResult AnnotationTransform::rotate90(const cv::Mat& image, const ImageAnnotation& annotation) {
    TransformResult out;
    cv::rotate(image, out.image, cv::ROTATE_90_CLOCKWISE);
    out.annotation = rotateAnnotation(annotation, image.rows, image.cols, [&](Point2D& p) { rotatePoint90(p, image.rows); });
    for (auto& object : out.annotation.objects) {
        if (object.hasMask && !object.mask.empty()) {
            cv::rotate(object.mask, object.mask, cv::ROTATE_90_CLOCKWISE);
        }
    }
    return out;
}

TransformResult AnnotationTransform::rotate180(const cv::Mat& image, const ImageAnnotation& annotation) {
    TransformResult out;
    cv::rotate(image, out.image, cv::ROTATE_180);
    out.annotation = rotateAnnotation(annotation, image.cols, image.rows, [&](Point2D& p) { rotatePoint180(p, image.cols, image.rows); });
    for (auto& object : out.annotation.objects) {
        if (object.hasMask && !object.mask.empty()) {
            cv::rotate(object.mask, object.mask, cv::ROTATE_180);
        }
    }
    return out;
}

TransformResult AnnotationTransform::rotate270(const cv::Mat& image, const ImageAnnotation& annotation) {
    TransformResult out;
    cv::rotate(image, out.image, cv::ROTATE_90_COUNTERCLOCKWISE);
    out.annotation = rotateAnnotation(annotation, image.rows, image.cols, [&](Point2D& p) { rotatePoint270(p, image.cols); });
    for (auto& object : out.annotation.objects) {
        if (object.hasMask && !object.mask.empty()) {
            cv::rotate(object.mask, object.mask, cv::ROTATE_90_COUNTERCLOCKWISE);
        }
    }
    return out;
}
