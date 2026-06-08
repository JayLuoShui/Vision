#pragma once

#include <opencv2/core.hpp>

#include <string>

struct ResizeConfig {
    int width = 640;
    int height = 640;
    bool keepAspect = false;
    cv::Scalar paddingColor = cv::Scalar(114, 114, 114);
};

struct TileConfig {
    int tileWidth = 640;
    int tileHeight = 640;
    int overlapX = 0;
    int overlapY = 0;
    bool padEdges = false;
    double keepVisibleRatio = 0.2;
};

struct CropConfig {
    int x = 0;
    int y = 0;
    int width = 640;
    int height = 640;
    double keepVisibleRatio = 0.2;
};

struct RenameConfig {
    std::string prefix = "img_";
    int startIndex = 1;
    int digits = 6;
    std::string outputExtension = ".jpg";
    int jpegQuality = 95;
};

struct TransformConfig {
    ResizeConfig resize;
    CropConfig crop;
    TileConfig tile;
    RenameConfig rename;
    bool enableResize = false;
    bool enableCrop = false;
    bool enableTiling = false;
    bool flipHorizontal = false;
    bool flipVertical = false;
    int rotateDegrees = 0;
    bool enableBrightnessContrast = false;
    double brightness = 0.0;
    double contrast = 1.0;
};
