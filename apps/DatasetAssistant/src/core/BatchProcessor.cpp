#include "core/BatchProcessor.h"

#include "core/AnnotationIO.h"
#include "core/AnnotationTransform.h"
#include "core/ImageProcessor.h"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <regex>
#include <sstream>
#include <unordered_map>

namespace fs = std::filesystem;

namespace {

struct ManifestEntry {
    std::string source;
    std::string output;
    std::string status;
    std::string error;
    std::string paramsHash;
};

struct FailedItem {
    std::string source;
    std::string error;
};

bool isImageFile(const fs::path& path) {
    std::string ext = path.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".bmp" || ext == ".webp";
}

std::string indexedName(const TransformConfig& config, int index, const std::string& suffix = "") {
    std::ostringstream ss;
    ss << config.rename.prefix << std::setw(config.rename.digits) << std::setfill('0') << index << suffix << config.rename.outputExtension;
    return ss.str();
}

std::string jsonEscape(std::string text) {
    std::string out;
    for (char ch : text) {
        if (ch == '\\') out += "\\\\";
        else if (ch == '"') out += "\\\"";
        else if (ch == '\n') out += "\\n";
        else out += ch;
    }
    return out;
}

std::string jsonUnescape(const std::string& text) {
    std::string out;
    out.reserve(text.size());
    bool escaping = false;
    for (char ch : text) {
        if (escaping) {
            if (ch == 'n') out += '\n';
            else out += ch;
            escaping = false;
        } else if (ch == '\\') {
            escaping = true;
        } else {
            out += ch;
        }
    }
    if (escaping) {
        out += '\\';
    }
    return out;
}

std::string pathKey(const fs::path& path) {
    return path.lexically_normal().generic_string();
}

std::string paramsHash(const ProjectConfig& config) {
    std::ostringstream ss;
    ss << static_cast<int>(config.annotationFormat) << '|'
       << static_cast<int>(config.outputAnnotationFormat) << '|';
    for (const auto& className : config.classNames) {
        ss << className << ',';
    }
    ss << '|'
       << config.transform.enableResize << '|'
       << config.transform.resize.width << 'x' << config.transform.resize.height << '|'
       << config.transform.resize.keepAspect << '|'
       << config.transform.resize.paddingColor[0] << ','
       << config.transform.resize.paddingColor[1] << ','
       << config.transform.resize.paddingColor[2] << '|'
       << config.transform.enableCrop << '|'
       << config.transform.crop.x << ',' << config.transform.crop.y << ','
       << config.transform.crop.width << 'x' << config.transform.crop.height << ','
       << config.transform.crop.keepVisibleRatio << '|'
       << config.transform.enableTiling << '|'
       << config.transform.tile.tileWidth << 'x' << config.transform.tile.tileHeight << '|'
       << config.transform.tile.overlapX << ',' << config.transform.tile.overlapY << '|'
       << config.transform.tile.padEdges << '|'
       << config.transform.tile.keepVisibleRatio << '|'
       << config.transform.flipHorizontal << '|' << config.transform.flipVertical << '|'
       << config.transform.rotateDegrees << '|'
       << config.transform.enableBrightnessContrast << '|'
       << config.transform.brightness << ',' << config.transform.contrast << '|'
       << config.transform.rename.prefix << '|'
       << config.transform.rename.digits << '|'
       << config.transform.rename.outputExtension << '|'
       << config.transform.rename.jpegQuality;
    return std::to_string(std::hash<std::string>{}(ss.str()));
}

std::string firstMatch(const std::string& text, const std::regex& pattern) {
    std::smatch match;
    if (std::regex_search(text, match, pattern) && match.size() > 1) {
        return match[1].str();
    }
    return {};
}

std::unordered_map<std::string, ManifestEntry> loadManifest(const fs::path& path) {
    std::unordered_map<std::string, ManifestEntry> entries;
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        return entries;
    }
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::regex objectPattern("\\{[^\\{\\}]*\"source\"[^\\{\\}]*\\}");
    for (std::sregex_iterator it(text.begin(), text.end(), objectPattern), end; it != end; ++it) {
        const std::string object = it->str();
        ManifestEntry entry;
        entry.source = jsonUnescape(firstMatch(object, std::regex("\"source\"\\s*:\\s*\"([^\"]*)\"")));
        entry.output = jsonUnescape(firstMatch(object, std::regex("\"output\"\\s*:\\s*\"([^\"]*)\"")));
        entry.status = jsonUnescape(firstMatch(object, std::regex("\"status\"\\s*:\\s*\"([^\"]*)\"")));
        entry.error = jsonUnescape(firstMatch(object, std::regex("\"error\"\\s*:\\s*\"([^\"]*)\"")));
        entry.paramsHash = jsonUnescape(firstMatch(object, std::regex("\"params_hash\"\\s*:\\s*\"([^\"]*)\"")));
        if (!entry.source.empty()) {
            entries[entry.source] = entry;
        }
    }
    return entries;
}

void saveManifest(const fs::path& path, const std::vector<ManifestEntry>& entries) {
    fs::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary);
    out << "{\n  \"items\": [\n";
    for (size_t i = 0; i < entries.size(); ++i) {
        if (i) {
            out << ",\n";
        }
        out << "    {\"source\":\"" << jsonEscape(entries[i].source)
            << "\",\"output\":\"" << jsonEscape(entries[i].output)
            << "\",\"status\":\"" << jsonEscape(entries[i].status)
            << "\",\"error\":\"" << jsonEscape(entries[i].error)
            << "\",\"params_hash\":\"" << jsonEscape(entries[i].paramsHash)
            << "\"}";
    }
    out << "\n  ]\n}\n";
}

void saveFailedItems(const fs::path& path, const std::vector<FailedItem>& items) {
    fs::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary);
    out << "source,error\n";
    for (const auto& item : items) {
        out << '"' << jsonEscape(item.source) << "\",\"" << jsonEscape(item.error) << "\"\n";
    }
}

fs::path labelForImage(const fs::path& labelDir, const fs::path& imagePath) {
    return labelDir / imagePath.stem().concat(".txt");
}

fs::path vocForImage(const fs::path& labelDir, const fs::path& imagePath) {
    return labelDir / imagePath.stem().concat(".xml");
}

fs::path maskForImage(const fs::path& labelDir, const fs::path& imagePath) {
    return labelDir / imagePath.stem().concat(".png");
}

std::string classNameFromId(int id, const std::vector<std::string>& classNames) {
    if (id >= 0 && id < static_cast<int>(classNames.size())) {
        return classNames[id];
    }
    return std::to_string(id);
}

fs::path cocoAnnotationFile(const fs::path& annotationPath) {
    if (fs::is_regular_file(annotationPath)) {
        return annotationPath;
    }
    for (const auto& name : {"instances.json", "annotations.json", "coco.json"}) {
        const fs::path candidate = annotationPath / name;
        if (fs::exists(candidate)) {
            return candidate;
        }
    }
    return {};
}

std::unordered_map<std::string, ImageAnnotation> loadCocoAnnotationsByImage(
    const fs::path& annotationPath,
    const std::vector<std::string>& classNames
) {
    std::unordered_map<std::string, ImageAnnotation> byImage;
    const fs::path cocoPath = cocoAnnotationFile(annotationPath);
    if (cocoPath.empty()) {
        return byImage;
    }
    for (auto annotation : AnnotationIO::loadCoco(cocoPath, classNames)) {
        const fs::path imagePath = annotation.imagePath;
        if (!imagePath.filename().empty()) {
            byImage[imagePath.filename().string()] = annotation;
        }
        if (!imagePath.stem().empty()) {
            byImage[imagePath.stem().string()] = annotation;
        }
    }
    return byImage;
}

ImageAnnotation annotationFromMask(
    const cv::Mat& inputMask,
    const fs::path& imagePath,
    int width,
    int height,
    const std::vector<std::string>& classNames
) {
    ImageAnnotation annotation;
    annotation.imagePath = imagePath;
    annotation.width = width;
    annotation.height = height;
    if (inputMask.empty()) {
        return annotation;
    }

    cv::Mat mask;
    if (inputMask.channels() == 1) {
        mask = inputMask;
    } else {
        std::vector<cv::Mat> channels;
        cv::split(inputMask, channels);
        mask = channels.front();
    }
    if (mask.size() != cv::Size(width, height)) {
        cv::resize(mask, mask, cv::Size(width, height), 0, 0, cv::INTER_NEAREST);
    }
    if (mask.depth() != CV_8U) {
        mask.convertTo(mask, CV_8U);
    }

    double minValue = 0.0;
    double maxValue = 0.0;
    cv::minMaxLoc(mask, &minValue, &maxValue);
    for (int value = 1; value <= static_cast<int>(maxValue); ++value) {
        cv::Mat classMask = mask == value;
        if (cv::countNonZero(classMask) == 0) {
            continue;
        }
        cv::Mat labels;
        cv::Mat stats;
        cv::Mat centroids;
        const int components = cv::connectedComponentsWithStats(classMask, labels, stats, centroids, 8, CV_32S);
        for (int component = 1; component < components; ++component) {
            const int area = stats.at<int>(component, cv::CC_STAT_AREA);
            if (area <= 0) {
                continue;
            }
            const int x = stats.at<int>(component, cv::CC_STAT_LEFT);
            const int y = stats.at<int>(component, cv::CC_STAT_TOP);
            const int w = stats.at<int>(component, cv::CC_STAT_WIDTH);
            const int h = stats.at<int>(component, cv::CC_STAT_HEIGHT);

            AnnotationObject object;
            object.classId = value - 1;
            object.className = classNameFromId(object.classId, classNames);
            object.box = {static_cast<double>(x), static_cast<double>(y), static_cast<double>(x + w), static_cast<double>(y + h)};
            object.hasMask = true;
            object.mask = labels == component;
            annotation.objects.push_back(object);
        }
    }
    return annotation;
}

void writeImage(const cv::Mat& image, const fs::path& imagePath, const TransformConfig& config) {
    fs::create_directories(imagePath.parent_path());
    std::vector<int> params;
    std::string ext = imagePath.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    if (ext == ".jpg" || ext == ".jpeg") {
        params = {cv::IMWRITE_JPEG_QUALITY, config.rename.jpegQuality};
    }
    if (!cv::imwrite(imagePath.string(), image, params)) {
        throw std::runtime_error("failed to write image: " + imagePath.string());
    }
}

cv::Mat rasterizeMask(const ImageAnnotation& annotation) {
    cv::Mat mask = cv::Mat::zeros(annotation.height, annotation.width, CV_8UC1);
    for (const auto& object : annotation.objects) {
        const uchar value = static_cast<uchar>(std::max(0, object.classId) + 1);
        if (object.hasMask && !object.mask.empty()) {
            cv::Mat resized;
            if (object.mask.size() == mask.size()) {
                resized = object.mask;
            } else {
                cv::resize(object.mask, resized, mask.size(), 0, 0, cv::INTER_NEAREST);
            }
            mask.setTo(value, resized > 0);
            continue;
        }
        if (object.hasPolygon && !object.polygons.empty()) {
            for (const auto& polygon : object.polygons) {
                std::vector<cv::Point> points;
                for (const auto& point : polygon.points) {
                    points.emplace_back(static_cast<int>(std::round(point.x)), static_cast<int>(std::round(point.y)));
                }
                if (points.size() >= 3) {
                    cv::fillPoly(mask, std::vector<std::vector<cv::Point>>{points}, cv::Scalar(value));
                }
            }
            continue;
        }
        cv::Rect rect(
            static_cast<int>(std::round(object.box.x1)),
            static_cast<int>(std::round(object.box.y1)),
            static_cast<int>(std::round(object.box.x2 - object.box.x1)),
            static_cast<int>(std::round(object.box.y2 - object.box.y1))
        );
        rect &= cv::Rect(0, 0, annotation.width, annotation.height);
        if (rect.area() > 0) {
            mask(rect).setTo(value);
        }
    }
    return mask;
}

void savePair(
    const cv::Mat& image,
    ImageAnnotation annotation,
    const fs::path& imagePath,
    const fs::path& labelDir,
    const TransformConfig& config,
    const std::vector<std::string>& classNames,
    AnnotationFormat outputFormat
) {
    annotation.imagePath = imagePath;
    annotation.width = image.cols;
    annotation.height = image.rows;
    writeImage(image, imagePath, config);
    fs::create_directories(labelDir);
    if (outputFormat == AnnotationFormat::Voc) {
        AnnotationIO::saveVoc(annotation, labelDir / imagePath.stem().concat(".xml"));
    } else if (outputFormat == AnnotationFormat::MaskPng) {
        const fs::path maskPath = labelDir / imagePath.stem().concat(".png");
        AnnotationIO::saveMaskPng(rasterizeMask(annotation), maskPath, labelDir / imagePath.stem().concat(".json"), classNames);
    } else if (outputFormat == AnnotationFormat::Yolo) {
        AnnotationIO::saveYolo(annotation, labelDir / imagePath.stem().concat(".txt"), classNames, true);
    }
}

fs::path primaryAnnotationPath(const fs::path& labelDir, const fs::path& imagePath, AnnotationFormat outputFormat) {
    if (outputFormat == AnnotationFormat::Voc) {
        return labelDir / imagePath.stem().concat(".xml");
    }
    if (outputFormat == AnnotationFormat::MaskPng) {
        return labelDir / imagePath.stem().concat(".png");
    }
    if (outputFormat == AnnotationFormat::Yolo) {
        return labelDir / imagePath.stem().concat(".txt");
    }
    return imagePath;
}

bool outputExistsFor(
    const fs::path& imagePath,
    const fs::path& labelDir,
    const fs::path& annotationDir,
    AnnotationFormat outputFormat
) {
    if (!fs::exists(imagePath)) {
        return false;
    }
    if (outputFormat == AnnotationFormat::Coco) {
        return fs::exists(annotationDir / "instances.json");
    }
    return fs::exists(primaryAnnotationPath(labelDir, imagePath, outputFormat));
}

cv::Size sizeBeforeTiling(const cv::Size& sourceSize, const TransformConfig& config) {
    cv::Size size = sourceSize;
    if (config.enableResize && config.resize.width > 0 && config.resize.height > 0) {
        size = cv::Size(config.resize.width, config.resize.height);
    }
    if (config.enableCrop && config.crop.width > 0 && config.crop.height > 0) {
        const cv::Rect imageRect(0, 0, size.width, size.height);
        const cv::Rect cropRect(config.crop.x, config.crop.y, config.crop.width, config.crop.height);
        const cv::Rect clipped = cropRect & imageRect;
        size = cv::Size(clipped.width, clipped.height);
    }
    const int rotate = ((config.rotateDegrees % 360) + 360) % 360;
    if (rotate == 90 || rotate == 270) {
        size = cv::Size(size.height, size.width);
    }
    return size;
}

bool allTileOutputsExist(
    const fs::path& imagePath,
    const ProjectConfig& config,
    int outputIndex,
    const fs::path& imageOutputDir,
    const fs::path& labelOutputDir,
    const fs::path& annotationOutputDir
) {
    if (!config.transform.enableTiling) {
        return outputExistsFor(
            imageOutputDir / indexedName(config.transform, outputIndex),
            labelOutputDir,
            annotationOutputDir,
            config.outputAnnotationFormat
        );
    }
    if (config.outputAnnotationFormat == AnnotationFormat::Coco) {
        return false;
    }

    cv::Mat image = cv::imread(imagePath.string(), cv::IMREAD_COLOR);
    if (image.empty()) {
        return false;
    }
    const cv::Size size = sizeBeforeTiling(image.size(), config.transform);
    const int tileWidth = config.transform.tile.tileWidth;
    const int tileHeight = config.transform.tile.tileHeight;
    if (size.width <= 0 || size.height <= 0 || tileWidth <= 0 || tileHeight <= 0) {
        return false;
    }

    const int stepX = std::max(1, tileWidth - config.transform.tile.overlapX);
    const int stepY = std::max(1, tileHeight - config.transform.tile.overlapY);
    int tileIndex = 0;
    for (int y = 0; y < size.height; y += stepY) {
        for (int x = 0; x < size.width; x += stepX) {
            if (!config.transform.tile.padEdges && (x + tileWidth > size.width || y + tileHeight > size.height)) {
                continue;
            }
            const fs::path tileImage = imageOutputDir / indexedName(config.transform, outputIndex, "_tile_" + std::to_string(tileIndex++));
            if (!outputExistsFor(tileImage, labelOutputDir, annotationOutputDir, config.outputAnnotationFormat)) {
                return false;
            }
        }
    }
    return tileIndex > 0;
}

std::unordered_map<std::string, ImageAnnotation>::const_iterator findAnnotationForImage(
    const std::unordered_map<std::string, ImageAnnotation>& annotations,
    const fs::path& imagePath
) {
    auto found = annotations.find(imagePath.filename().string());
    if (found != annotations.end()) {
        return found;
    }
    return annotations.find(imagePath.stem().string());
}

}  // namespace

BatchProcessSummary BatchProcessor::processImages(const ProjectConfig& config) {
    BatchProcessSummary summary;
    const fs::path failedItemsPath = config.outputDir / "processed" / "failed_items.csv";
    if (!fs::exists(config.imageInputDir)) {
        summary.errors.push_back("image input dir not found: " + config.imageInputDir.string());
        summary.failedItems++;
        saveFailedItems(failedItemsPath, {{pathKey(config.imageInputDir), "image input dir not found"}});
        return summary;
    }

    const fs::path imageOutputDir = config.outputDir / "processed" / "images";
    const fs::path labelOutputDir = config.outputDir / "processed" / "labels";
    const fs::path annotationOutputDir = config.outputDir / "processed" / "annotations";
    const fs::path manifestPath = config.outputDir / "processed" / "task_manifest.json";
    const std::string currentHash = paramsHash(config);
    const auto previousManifest = loadManifest(manifestPath);
    const auto cocoAnnotations = config.annotationFormat == AnnotationFormat::Coco
        ? loadCocoAnnotationsByImage(config.annotationDir, config.classNames)
        : std::unordered_map<std::string, ImageAnnotation>{};
    const auto existingOutputCocoAnnotations = config.outputAnnotationFormat == AnnotationFormat::Coco
        ? loadCocoAnnotationsByImage(annotationOutputDir, config.classNames)
        : std::unordered_map<std::string, ImageAnnotation>{};
    std::vector<ManifestEntry> manifestEntries;
    std::vector<ImageAnnotation> outputCocoAnnotations;
    std::vector<FailedItem> failedItems;

    std::vector<fs::path> images;
    for (const auto& entry : fs::directory_iterator(config.imageInputDir)) {
        if (entry.is_regular_file() && isImageFile(entry.path())) {
            images.push_back(entry.path());
        }
    }
    std::sort(images.begin(), images.end());

    for (size_t imageOrdinal = 0; imageOrdinal < images.size(); ++imageOrdinal) {
        const auto& imagePath = images[imageOrdinal];
        const int outputIndex = config.transform.rename.startIndex + static_cast<int>(imageOrdinal);
        ManifestEntry manifestEntry;
        manifestEntry.source = pathKey(imagePath);
        manifestEntry.paramsHash = currentHash;
        try {
            fs::path primaryOutput = imageOutputDir / indexedName(config.transform, outputIndex);
            auto previous = previousManifest.find(pathKey(imagePath));
            const bool previousOutputReady = previous != previousManifest.end() &&
                previous->second.status == "done" &&
                previous->second.paramsHash == currentHash &&
                allTileOutputsExist(imagePath, config, outputIndex, imageOutputDir, labelOutputDir, annotationOutputDir);
            auto previousCocoAnnotation = existingOutputCocoAnnotations.end();
            if (previousOutputReady && config.outputAnnotationFormat == AnnotationFormat::Coco) {
                previousCocoAnnotation = findAnnotationForImage(existingOutputCocoAnnotations, previous->second.output);
            }
            const bool canReusePrevious = previousOutputReady &&
                (config.outputAnnotationFormat != AnnotationFormat::Coco ||
                 previousCocoAnnotation != existingOutputCocoAnnotations.end());
            if (canReusePrevious) {
                manifestEntry.output = previous->second.output;
                manifestEntry.status = "done";
                if (config.outputAnnotationFormat == AnnotationFormat::Coco) {
                    outputCocoAnnotations.push_back(previousCocoAnnotation->second);
                }
                summary.skippedImages++;
                manifestEntries.push_back(manifestEntry);
                continue;
            }

            cv::Mat image = cv::imread(imagePath.string(), cv::IMREAD_COLOR);
            if (image.empty()) {
                throw std::runtime_error("failed to read image: " + imagePath.string());
            }

            ImageAnnotation annotation;
            const fs::path yoloPath = labelForImage(config.annotationDir, imagePath);
            const fs::path vocPath = vocForImage(config.annotationDir, imagePath);
            const fs::path maskPath = maskForImage(config.annotationDir, imagePath);
            if (config.annotationFormat == AnnotationFormat::Yolo && fs::exists(yoloPath)) {
                annotation = AnnotationIO::loadYolo(yoloPath, imagePath, image.cols, image.rows, config.classNames);
            } else if (config.annotationFormat == AnnotationFormat::Voc && fs::exists(vocPath)) {
                annotation = AnnotationIO::loadVoc(vocPath, config.classNames);
                annotation.imagePath = imagePath;
            } else if (config.annotationFormat == AnnotationFormat::Coco) {
                auto found = findAnnotationForImage(cocoAnnotations, imagePath);
                if (found != cocoAnnotations.end()) {
                    annotation = found->second;
                    annotation.imagePath = imagePath;
                    annotation.width = image.cols;
                    annotation.height = image.rows;
                } else {
                    annotation.imagePath = imagePath;
                    annotation.width = image.cols;
                    annotation.height = image.rows;
                }
            } else if (config.annotationFormat == AnnotationFormat::MaskPng && fs::exists(maskPath)) {
                annotation = annotationFromMask(AnnotationIO::loadMaskPng(maskPath), imagePath, image.cols, image.rows, config.classNames);
            } else {
                annotation.imagePath = imagePath;
                annotation.width = image.cols;
                annotation.height = image.rows;
            }

            TransformResult current{image, annotation};
            if (config.transform.enableResize) {
                if (config.transform.resize.keepAspect) {
                    current = AnnotationTransform::letterbox(
                        current.image,
                        current.annotation,
                        config.transform.resize.width,
                        config.transform.resize.height,
                        config.transform.resize.paddingColor
                    );
                } else {
                    current = AnnotationTransform::resize(current.image, current.annotation, config.transform.resize.width, config.transform.resize.height);
                }
            }
            if (config.transform.enableCrop) {
                current = AnnotationTransform::crop(
                    current.image,
                    current.annotation,
                    {config.transform.crop.x, config.transform.crop.y, config.transform.crop.width, config.transform.crop.height},
                    config.transform.crop.keepVisibleRatio
                );
            }
            if (config.transform.flipHorizontal) {
                current = AnnotationTransform::flipHorizontal(current.image, current.annotation);
            }
            if (config.transform.flipVertical) {
                current = AnnotationTransform::flipVertical(current.image, current.annotation);
            }
            if (config.transform.rotateDegrees == 90) {
                current = AnnotationTransform::rotate90(current.image, current.annotation);
            } else if (config.transform.rotateDegrees == 180) {
                current = AnnotationTransform::rotate180(current.image, current.annotation);
            } else if (config.transform.rotateDegrees == 270) {
                current = AnnotationTransform::rotate270(current.image, current.annotation);
            }
            if (config.transform.enableBrightnessContrast) {
                current.image = ImageProcessor::adjustBrightnessContrast(current.image, config.transform.brightness, config.transform.contrast);
            }

            if (config.transform.enableTiling) {
                auto tiles = AnnotationTransform::tile(
                    current.image,
                    current.annotation,
                    config.transform.tile.tileWidth,
                    config.transform.tile.tileHeight,
                    config.transform.tile.overlapX,
                    config.transform.tile.overlapY,
                    config.transform.tile.padEdges,
                    config.transform.tile.keepVisibleRatio
                );
                int tileIndex = 0;
                for (auto& tile : tiles) {
                    const std::string stem = indexedName(config.transform, outputIndex, "_tile_" + std::to_string(tileIndex++));
                    fs::path outImage = imageOutputDir / stem;
                    savePair(tile.image, tile.annotation, outImage, labelOutputDir, config.transform, config.classNames, config.outputAnnotationFormat);
                    if (config.outputAnnotationFormat == AnnotationFormat::Coco) {
                        tile.annotation.imagePath = outImage;
                        tile.annotation.width = tile.image.cols;
                        tile.annotation.height = tile.image.rows;
                        outputCocoAnnotations.push_back(tile.annotation);
                    }
                    summary.processedImages++;
                }
                manifestEntry.output = pathKey(imageOutputDir / indexedName(config.transform, outputIndex, "_tile_0"));
            } else {
                fs::path outImage = primaryOutput;
                savePair(current.image, current.annotation, outImage, labelOutputDir, config.transform, config.classNames, config.outputAnnotationFormat);
                if (config.outputAnnotationFormat == AnnotationFormat::Coco) {
                    current.annotation.imagePath = outImage;
                    current.annotation.width = current.image.cols;
                    current.annotation.height = current.image.rows;
                    outputCocoAnnotations.push_back(current.annotation);
                }
                summary.processedImages++;
                manifestEntry.output = pathKey(outImage);
            }
            manifestEntry.status = "done";
        } catch (const std::exception& ex) {
            summary.failedItems++;
            summary.errors.push_back(imagePath.string() + ": " + ex.what());
            failedItems.push_back({pathKey(imagePath), ex.what()});
            manifestEntry.output.clear();
            manifestEntry.status = "failed";
            manifestEntry.error = ex.what();
        }
        manifestEntries.push_back(manifestEntry);
    }

    fs::create_directories(config.outputDir / "processed");
    if (config.outputAnnotationFormat == AnnotationFormat::Coco) {
        fs::create_directories(annotationOutputDir);
        AnnotationIO::saveCoco(outputCocoAnnotations, annotationOutputDir / "instances.json", config.classNames);
    }
    std::ofstream out(config.outputDir / "processed" / "summary.json");
    out << "{\n";
    out << "  \"processed_images\": " << summary.processedImages << ",\n";
    out << "  \"skipped_images\": " << summary.skippedImages << ",\n";
    out << "  \"failed_items\": " << summary.failedItems << "\n";
    out << "}\n";
    saveManifest(manifestPath, manifestEntries);
    saveFailedItems(failedItemsPath, failedItems);
    return summary;
}
