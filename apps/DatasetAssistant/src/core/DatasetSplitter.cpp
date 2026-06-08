#include "core/DatasetSplitter.h"

#include "core/AnnotationIO.h"

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cmath>
#include <fstream>
#include <map>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;

namespace {

bool isImage(const fs::path& path) {
    std::string ext = path.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return ext == ".jpg" || ext == ".jpeg" || ext == ".png" || ext == ".bmp" || ext == ".webp";
}

fs::path labelPathFor(const fs::path& labelDir, const fs::path& imagePath, AnnotationFormat format) {
    if (format == AnnotationFormat::Voc) {
        return labelDir / imagePath.stem().concat(".xml");
    }
    if (format == AnnotationFormat::MaskPng) {
        return labelDir / imagePath.stem().concat(".png");
    }
    if (format == AnnotationFormat::Coco) {
        if (fs::is_regular_file(labelDir)) {
            return labelDir;
        }
        for (const auto& name : {"instances.json", "annotations.json", "coco.json"}) {
            const fs::path candidate = labelDir / name;
            if (fs::exists(candidate)) {
                return candidate;
            }
        }
        return {};
    }
    return labelDir / imagePath.stem().concat(".txt");
}

std::set<std::string> cocoAnnotatedImages(const fs::path& labelDir, const std::vector<std::string>& classNames) {
    std::set<std::string> annotated;
    const fs::path cocoPath = labelPathFor(labelDir, {}, AnnotationFormat::Coco);
    if (cocoPath.empty()) {
        return annotated;
    }
    for (const auto& annotation : AnnotationIO::loadCoco(cocoPath, classNames)) {
        if (!annotation.imagePath.filename().empty()) {
            annotated.insert(annotation.imagePath.filename().string());
        }
        if (!annotation.imagePath.stem().empty()) {
            annotated.insert(annotation.imagePath.stem().string());
        }
    }
    return annotated;
}

bool yoloHasObjects(const fs::path& labelPath, const fs::path& imagePath, const std::vector<std::string>& classNames) {
    cv::Mat image = cv::imread(imagePath.string(), cv::IMREAD_COLOR);
    if (image.empty()) {
        return false;
    }
    try {
        return !AnnotationIO::loadYolo(labelPath, imagePath, image.cols, image.rows, classNames).objects.empty();
    } catch (...) {
        return false;
    }
}

bool vocHasObjects(const fs::path& labelPath, const std::vector<std::string>& classNames) {
    try {
        return !AnnotationIO::loadVoc(labelPath, classNames).objects.empty();
    } catch (...) {
        return false;
    }
}

bool maskHasObjects(const fs::path& labelPath) {
    cv::Mat mask = AnnotationIO::loadMaskPng(labelPath);
    if (mask.empty()) {
        return false;
    }
    if (mask.channels() > 1) {
        std::vector<cv::Mat> channels;
        cv::split(mask, channels);
        mask = channels.front();
    }
    return cv::countNonZero(mask) > 0;
}

bool annotationFileHasObjects(
    const fs::path& labelPath,
    const fs::path& imagePath,
    AnnotationFormat format,
    const std::vector<std::string>& classNames
) {
    if (labelPath.empty() || !fs::exists(labelPath)) {
        return false;
    }
    if (format == AnnotationFormat::Voc) {
        return vocHasObjects(labelPath, classNames);
    }
    if (format == AnnotationFormat::MaskPng) {
        return maskHasObjects(labelPath);
    }
    if (format == AnnotationFormat::Yolo) {
        return yoloHasObjects(labelPath, imagePath, classNames);
    }
    return fs::file_size(labelPath) > 0;
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

    double maxValue = 0.0;
    cv::minMaxLoc(mask, nullptr, &maxValue);
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
            object.className = object.classId >= 0 && object.classId < static_cast<int>(classNames.size())
                ? classNames[object.classId]
                : std::to_string(object.classId);
            object.box = {static_cast<double>(x), static_cast<double>(y), static_cast<double>(x + w), static_cast<double>(y + h)};
            object.hasMask = true;
            object.mask = labels == component;
            annotation.objects.push_back(object);
        }
    }
    return annotation;
}

ImageAnnotation loadAnnotationForItem(const DatasetItem& item, const SplitConfig& config) {
    cv::Mat image = cv::imread(item.imagePath.string(), cv::IMREAD_COLOR);
    ImageAnnotation annotation;
    annotation.imagePath = item.imagePath;
    annotation.width = image.empty() ? 0 : image.cols;
    annotation.height = image.empty() ? 0 : image.rows;
    if (!item.hasAnnotation || annotation.width <= 0 || annotation.height <= 0) {
        return annotation;
    }
    if (config.sourceAnnotationFormat == AnnotationFormat::Voc) {
        annotation = AnnotationIO::loadVoc(item.annotationPath, config.classNames);
        annotation.imagePath = item.imagePath;
        annotation.width = image.cols;
        annotation.height = image.rows;
    } else if (config.sourceAnnotationFormat == AnnotationFormat::Coco) {
        for (auto candidate : AnnotationIO::loadCoco(item.annotationPath, config.classNames)) {
            if (candidate.imagePath.filename() == item.imagePath.filename() || candidate.imagePath.stem() == item.imagePath.stem()) {
                candidate.imagePath = item.imagePath;
                candidate.width = image.cols;
                candidate.height = image.rows;
                return candidate;
            }
        }
    } else if (config.sourceAnnotationFormat == AnnotationFormat::MaskPng) {
        annotation = annotationFromMask(AnnotationIO::loadMaskPng(item.annotationPath), item.imagePath, image.cols, image.rows, config.classNames);
    } else {
        annotation = AnnotationIO::loadYolo(item.annotationPath, item.imagePath, annotation.width, annotation.height, config.classNames);
    }
    return annotation;
}

cv::Mat rasterizeMask(const ImageAnnotation& annotation) {
    cv::Mat mask = cv::Mat::zeros(annotation.height, annotation.width, CV_8UC1);
    for (const auto& object : annotation.objects) {
        const uchar value = static_cast<uchar>(std::max(0, object.classId) + 1);
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

std::string csvEscape(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size());
    for (const char ch : value) {
        if (ch == '"') {
            escaped += "\"\"";
        } else {
            escaped += ch;
        }
    }
    return "\"" + escaped + "\"";
}

void appendFailedItem(const fs::path& outputDir, const fs::path& source, const std::string& error) {
    fs::create_directories(outputDir);
    const fs::path failedPath = outputDir / "failed_items.csv";
    const bool writeHeader = !fs::exists(failedPath) || fs::file_size(failedPath) == 0;
    std::ofstream out(failedPath, std::ios::app);
    if (writeHeader) {
        out << "source,error\n";
    }
    out << csvEscape(source.u8string()) << "," << csvEscape(error) << "\n";
}

bool copyImageLogged(const DatasetItem& item, const fs::path& target, const fs::path& outputDir) {
    try {
        fs::create_directories(target.parent_path());
        fs::copy_file(item.imagePath, target, fs::copy_options::overwrite_existing);
        return true;
    } catch (const std::exception& error) {
        appendFailedItem(outputDir, item.imagePath, std::string("copy image failed: ") + error.what());
        return false;
    }
}

void copySubset(const std::vector<DatasetItem>& items, const fs::path& outputDir, const std::string& splitName, const SplitConfig& config) {
    fs::create_directories(outputDir / "images" / splitName);
    fs::create_directories(outputDir / "labels" / splitName);
    for (const auto& item : items) {
        if (!copyImageLogged(item, outputDir / "images" / splitName / item.imagePath.filename(), outputDir)) {
            continue;
        }
        const fs::path labelTarget = outputDir / "labels" / splitName / item.imagePath.stem().concat(".txt");
        try {
            if (item.hasAnnotation && fs::exists(item.annotationPath) && config.sourceAnnotationFormat == AnnotationFormat::Yolo) {
                fs::copy_file(item.annotationPath, labelTarget, fs::copy_options::overwrite_existing);
            } else if (item.hasAnnotation) {
                AnnotationIO::saveYolo(loadAnnotationForItem(item, config), labelTarget, config.classNames, true);
            } else {
                std::ofstream(labelTarget);
            }
        } catch (const std::exception& error) {
            appendFailedItem(outputDir, item.annotationPath, std::string("copy label failed: ") + error.what());
        }
    }
}

size_t objectCount(const std::vector<DatasetItem>& items, const SplitConfig& config) {
    size_t count = 0;
    for (const auto& item : items) {
        if (!item.hasAnnotation) {
            continue;
        }
        count += loadAnnotationForItem(item, config).objects.size();
    }
    return count;
}

std::map<int, size_t> classDistribution(const SplitResult& split, const SplitConfig& config) {
    std::map<int, size_t> distribution;
    const auto collect = [&distribution, &config](const std::vector<DatasetItem>& items) {
        for (const auto& item : items) {
            if (!item.hasAnnotation) {
                continue;
            }
            for (const auto& object : loadAnnotationForItem(item, config).objects) {
                distribution[object.classId]++;
            }
        }
    };
    collect(split.train);
    collect(split.val);
    collect(split.test);
    return distribution;
}

void writeSummary(const SplitResult& split, const fs::path& outputDir, const SplitConfig& config, const std::string& formatName) {
    const auto distribution = classDistribution(split, config);
    std::ofstream summary(outputDir / "summary.json");
    summary << "{\n";
    summary << "  \"format\": \"" << formatName << "\",\n";
    summary << "  \"train_images\": " << split.train.size() << ",\n";
    summary << "  \"val_images\": " << split.val.size() << ",\n";
    summary << "  \"test_images\": " << split.test.size() << ",\n";
    summary << "  \"train_objects\": " << objectCount(split.train, config) << ",\n";
    summary << "  \"val_objects\": " << objectCount(split.val, config) << ",\n";
    summary << "  \"test_objects\": " << objectCount(split.test, config) << ",\n";
    summary << "  \"include_negative\": " << (config.includeNegative ? "true" : "false") << ",\n";
    summary << "  \"train_ratio\": " << config.trainRatio << ",\n";
    summary << "  \"val_ratio\": " << config.valRatio << ",\n";
    summary << "  \"test_ratio\": " << config.testRatio << ",\n";
    summary << "  \"seed\": " << config.seed << ",\n";
    summary << "  \"class_distribution\": {\n";
    for (size_t i = 0; i < config.classNames.size(); ++i) {
        const auto found = distribution.find(static_cast<int>(i));
        summary << "    \"" << config.classNames[i] << "\": {\"id\": " << i << ", \"total\": "
                << (found == distribution.end() ? 0 : found->second) << "}";
        if (i + 1 < config.classNames.size()) {
            summary << ",";
        }
        summary << "\n";
    }
    summary << "  }\n";
    summary << "}\n";
}

void copyImagesFlat(const std::vector<DatasetItem>& items, const fs::path& outputDir, const std::string& splitName) {
    fs::create_directories(outputDir / splitName / "images");
    for (const auto& item : items) {
        copyImageLogged(item, outputDir / splitName / "images" / item.imagePath.filename(), outputDir);
    }
}

void exportVocSubset(const std::vector<DatasetItem>& items, const fs::path& outputDir, const std::string& splitName, const SplitConfig& config) {
    fs::create_directories(outputDir / splitName / "images");
    fs::create_directories(outputDir / splitName / "annotations");
    for (const auto& item : items) {
        if (!copyImageLogged(item, outputDir / splitName / "images" / item.imagePath.filename(), outputDir)) {
            continue;
        }
        ImageAnnotation annotation = loadAnnotationForItem(item, config);
        annotation.imagePath = item.imagePath;
        AnnotationIO::saveVoc(annotation, outputDir / splitName / "annotations" / item.imagePath.stem().concat(".xml"));
    }
}

void exportMaskSubset(const std::vector<DatasetItem>& items, const fs::path& outputDir, const std::string& splitName, const SplitConfig& config) {
    fs::create_directories(outputDir / splitName / "images");
    fs::create_directories(outputDir / splitName / "masks");
    for (const auto& item : items) {
        if (!copyImageLogged(item, outputDir / splitName / "images" / item.imagePath.filename(), outputDir)) {
            continue;
        }
        ImageAnnotation annotation = loadAnnotationForItem(item, config);
        if (annotation.width <= 0 || annotation.height <= 0) {
            continue;
        }
        AnnotationIO::saveMaskPng(
            rasterizeMask(annotation),
            outputDir / splitName / "masks" / item.imagePath.stem().concat(".png"),
            outputDir / splitName / "masks" / item.imagePath.stem().concat(".json"),
            config.classNames
        );
    }
}

std::vector<ImageAnnotation> exportCocoSubset(const std::vector<DatasetItem>& items, const fs::path& outputDir, const std::string& splitName, const SplitConfig& config) {
    fs::create_directories(outputDir / splitName);
    std::vector<ImageAnnotation> annotations;
    for (const auto& item : items) {
        if (!copyImageLogged(item, outputDir / splitName / item.imagePath.filename(), outputDir)) {
            continue;
        }
        ImageAnnotation annotation = loadAnnotationForItem(item, config);
        annotation.imagePath = item.imagePath.filename();
        annotations.push_back(annotation);
    }
    return annotations;
}

}  // namespace

SplitResult DatasetSplitter::splitFiles(const fs::path& imageDir, const fs::path& labelDir, const SplitConfig& config) {
    std::vector<DatasetItem> items;
    if (!fs::exists(imageDir)) {
        return {};
    }
    for (const auto& entry : fs::directory_iterator(imageDir)) {
        if (!entry.is_regular_file() || !isImage(entry.path())) {
            continue;
        }
        fs::path label = labelPathFor(labelDir, entry.path(), config.sourceAnnotationFormat);
        bool hasLabel = false;
        if (config.sourceAnnotationFormat == AnnotationFormat::Coco) {
            const auto annotated = cocoAnnotatedImages(labelDir, config.classNames);
            hasLabel = !label.empty() && fs::exists(label) &&
                (annotated.count(entry.path().filename().string()) > 0 || annotated.count(entry.path().stem().string()) > 0);
        } else {
            hasLabel = annotationFileHasObjects(label, entry.path(), config.sourceAnnotationFormat, config.classNames);
        }
        if (!config.includeNegative && !hasLabel) {
            continue;
        }
        items.push_back({entry.path(), label, hasLabel});
    }
    std::sort(items.begin(), items.end(), [](const DatasetItem& a, const DatasetItem& b) {
        return a.imagePath.filename().string() < b.imagePath.filename().string();
    });
    std::mt19937 rng(config.seed);
    std::shuffle(items.begin(), items.end(), rng);

    const size_t trainCount = static_cast<size_t>(items.size() * config.trainRatio);
    const size_t valCount = static_cast<size_t>(items.size() * config.valRatio);
    SplitResult result;
    for (size_t i = 0; i < items.size(); ++i) {
        if (i < trainCount) {
            result.train.push_back(items[i]);
        } else if (i < trainCount + valCount) {
            result.val.push_back(items[i]);
        } else {
            result.test.push_back(items[i]);
        }
    }
    return result;
}

void DatasetSplitter::exportDataset(const SplitResult& split, const fs::path& outputDir, const SplitConfig& config) {
    if (config.format == DatasetFormat::Coco) {
        exportCoco(split, outputDir, config);
    } else if (config.format == DatasetFormat::Voc) {
        exportVoc(split, outputDir, config);
    } else if (config.format == DatasetFormat::MaskPng) {
        exportMaskPng(split, outputDir, config);
    } else {
        exportYolo(split, outputDir, config);
    }
}

void DatasetSplitter::exportYolo(const SplitResult& split, const fs::path& outputDir, const SplitConfig& config) {
    fs::create_directories(outputDir);
    copySubset(split.train, outputDir, "train", config);
    copySubset(split.val, outputDir, "val", config);
    copySubset(split.test, outputDir, "test", config);

    {
        std::ofstream yaml(outputDir / "data.yaml");
        yaml << "path: " << outputDir.lexically_normal().generic_string() << "\n";
        yaml << "train: images/train\nval: images/val\ntest: images/test\n";
        yaml << "names:\n";
        for (size_t i = 0; i < config.classNames.size(); ++i) {
            yaml << "  " << i << ": " << config.classNames[i] << "\n";
        }
    }
    writeSummary(split, outputDir, config, "yolo");
}

void DatasetSplitter::exportVoc(const SplitResult& split, const fs::path& outputDir, const SplitConfig& config) {
    fs::create_directories(outputDir);
    exportVocSubset(split.train, outputDir, "train", config);
    exportVocSubset(split.val, outputDir, "val", config);
    exportVocSubset(split.test, outputDir, "test", config);
    writeSummary(split, outputDir, config, "voc");
}

void DatasetSplitter::exportCoco(const SplitResult& split, const fs::path& outputDir, const SplitConfig& config) {
    fs::create_directories(outputDir / "annotations");
    auto train = exportCocoSubset(split.train, outputDir, "train", config);
    auto val = exportCocoSubset(split.val, outputDir, "val", config);
    auto test = exportCocoSubset(split.test, outputDir, "test", config);
    AnnotationIO::saveCoco(train, outputDir / "annotations" / "instances_train.json", config.classNames);
    AnnotationIO::saveCoco(val, outputDir / "annotations" / "instances_val.json", config.classNames);
    AnnotationIO::saveCoco(test, outputDir / "annotations" / "instances_test.json", config.classNames);
    writeSummary(split, outputDir, config, "coco");
}

void DatasetSplitter::exportMaskPng(const SplitResult& split, const fs::path& outputDir, const SplitConfig& config) {
    fs::create_directories(outputDir);
    exportMaskSubset(split.train, outputDir, "train", config);
    exportMaskSubset(split.val, outputDir, "val", config);
    exportMaskSubset(split.test, outputDir, "test", config);
    writeSummary(split, outputDir, config, "mask_png");
}
