#include "core/ProjectManager.h"
#include "core/RuntimePaths.h"

#include <fstream>
#include <regex>
#include <sstream>

namespace fs = std::filesystem;

namespace {

std::string jsonEscape(const std::string& text) {
    std::string out;
    for (char ch : text) {
        if (ch == '\\') out += "\\\\";
        else if (ch == '"') out += "\\\"";
        else out += ch;
    }
    return out;
}

std::string stringValue(const std::string& text, const std::string& key) {
    std::smatch match;
    if (std::regex_search(text, match, std::regex("\"" + key + "\"\\s*:\\s*\"([^\"]*)\""))) {
        return match[1].str();
    }
    return {};
}

double numberValue(const std::string& text, const std::string& key, double fallback) {
    std::smatch match;
    if (std::regex_search(text, match, std::regex("\"" + key + "\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?)"))) {
        return std::stod(match[1].str());
    }
    return fallback;
}

bool boolValue(const std::string& text, const std::string& key, bool fallback) {
    std::smatch match;
    if (std::regex_search(text, match, std::regex("\"" + key + "\"\\s*:\\s*(true|false)"))) {
        return match[1].str() == "true";
    }
    return fallback;
}

std::vector<std::string> stringArrayValue(const std::string& text, const std::string& key) {
    std::smatch match;
    std::vector<std::string> values;
    if (!std::regex_search(text, match, std::regex("\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]"))) {
        return values;
    }
    const std::string body = match[1].str();
    std::regex itemPattern("\"([^\"]*)\"");
    for (std::sregex_iterator it(body.begin(), body.end(), itemPattern), end; it != end; ++it) {
        values.push_back((*it)[1].str());
    }
    return values;
}

std::string annotationFormatName(AnnotationFormat format) {
    switch (format) {
        case AnnotationFormat::Coco: return "coco";
        case AnnotationFormat::Voc: return "voc";
        case AnnotationFormat::MaskPng: return "mask_png";
        case AnnotationFormat::Yolo:
        default: return "yolo";
    }
}

AnnotationFormat annotationFormatValue(const std::string& value, AnnotationFormat fallback) {
    if (value == "coco") return AnnotationFormat::Coco;
    if (value == "voc") return AnnotationFormat::Voc;
    if (value == "mask_png") return AnnotationFormat::MaskPng;
    if (value == "yolo") return AnnotationFormat::Yolo;
    return fallback;
}

std::string datasetFormatName(DatasetFormat format) {
    switch (format) {
        case DatasetFormat::Coco: return "coco";
        case DatasetFormat::Voc: return "voc";
        case DatasetFormat::MaskPng: return "mask_png";
        case DatasetFormat::Yolo:
        default: return "yolo";
    }
}

std::string devicePolicyName(DevicePolicy policy) {
    switch (policy) {
        case DevicePolicy::Cpu: return "cpu";
        case DevicePolicy::Gpu: return "gpu";
        case DevicePolicy::Auto:
        default: return "auto";
    }
}

DevicePolicy devicePolicyValue(const std::string& value, DevicePolicy fallback) {
    if (value == "cpu") return DevicePolicy::Cpu;
    if (value == "gpu") return DevicePolicy::Gpu;
    if (value == "auto") return DevicePolicy::Auto;
    return fallback;
}

DatasetFormat datasetFormatValue(const std::string& value, DatasetFormat fallback) {
    if (value == "coco") return DatasetFormat::Coco;
    if (value == "voc") return DatasetFormat::Voc;
    if (value == "mask_png") return DatasetFormat::MaskPng;
    if (value == "yolo") return DatasetFormat::Yolo;
    return fallback;
}

}  // namespace

ProjectConfig ProjectManager::createDefault(const fs::path& projectFile) {
    ProjectConfig config;
    config.projectFile = projectFile;
    config.outputDir = RuntimePaths::defaultOutputDir();
    config.classNames = {"object"};
    config.split.classNames = config.classNames;
    return config;
}

bool ProjectManager::save(const ProjectConfig& config, const fs::path& path) {
    if (!path.parent_path().empty()) {
        fs::create_directories(path.parent_path());
    }
    std::ofstream out(path);
    if (!out) {
        return false;
    }
    out << "{\n";
    out << "  \"image_input_dir\": \"" << jsonEscape(config.imageInputDir.string()) << "\",\n";
    out << "  \"video_input_path\": \"" << jsonEscape(config.videoInputPath.string()) << "\",\n";
    out << "  \"annotation_dir\": \"" << jsonEscape(config.annotationDir.string()) << "\",\n";
    out << "  \"output_dir\": \"" << jsonEscape(config.outputDir.string()) << "\",\n";
    out << "  \"annotation_format\": \"" << annotationFormatName(config.annotationFormat) << "\",\n";
    out << "  \"output_annotation_format\": \"" << annotationFormatName(config.outputAnnotationFormat) << "\",\n";
    out << "  \"class_names\": [";
    for (size_t i = 0; i < config.classNames.size(); ++i) {
        if (i) out << ", ";
        out << "\"" << jsonEscape(config.classNames[i]) << "\"";
    }
    out << "],\n";
    out << "  \"enable_resize\": " << (config.transform.enableResize ? "true" : "false") << ",\n";
    out << "  \"resize_width\": " << config.transform.resize.width << ",\n";
    out << "  \"resize_height\": " << config.transform.resize.height << ",\n";
    out << "  \"keep_aspect\": " << (config.transform.resize.keepAspect ? "true" : "false") << ",\n";
    out << "  \"padding_b\": " << config.transform.resize.paddingColor[0] << ",\n";
    out << "  \"padding_g\": " << config.transform.resize.paddingColor[1] << ",\n";
    out << "  \"padding_r\": " << config.transform.resize.paddingColor[2] << ",\n";
    out << "  \"enable_crop\": " << (config.transform.enableCrop ? "true" : "false") << ",\n";
    out << "  \"crop_x\": " << config.transform.crop.x << ",\n";
    out << "  \"crop_y\": " << config.transform.crop.y << ",\n";
    out << "  \"crop_width\": " << config.transform.crop.width << ",\n";
    out << "  \"crop_height\": " << config.transform.crop.height << ",\n";
    out << "  \"crop_keep_visible_ratio\": " << config.transform.crop.keepVisibleRatio << ",\n";
    out << "  \"enable_tiling\": " << (config.transform.enableTiling ? "true" : "false") << ",\n";
    out << "  \"tile_width\": " << config.transform.tile.tileWidth << ",\n";
    out << "  \"tile_height\": " << config.transform.tile.tileHeight << ",\n";
    out << "  \"overlap_x\": " << config.transform.tile.overlapX << ",\n";
    out << "  \"overlap_y\": " << config.transform.tile.overlapY << ",\n";
    out << "  \"tile_pad_edges\": " << (config.transform.tile.padEdges ? "true" : "false") << ",\n";
    out << "  \"tile_keep_visible_ratio\": " << config.transform.tile.keepVisibleRatio << ",\n";
    out << "  \"flip_horizontal\": " << (config.transform.flipHorizontal ? "true" : "false") << ",\n";
    out << "  \"flip_vertical\": " << (config.transform.flipVertical ? "true" : "false") << ",\n";
    out << "  \"rotate_degrees\": " << config.transform.rotateDegrees << ",\n";
    out << "  \"enable_brightness_contrast\": " << (config.transform.enableBrightnessContrast ? "true" : "false") << ",\n";
    out << "  \"brightness\": " << config.transform.brightness << ",\n";
    out << "  \"contrast\": " << config.transform.contrast << ",\n";
    out << "  \"rename_prefix\": \"" << jsonEscape(config.transform.rename.prefix) << "\",\n";
    out << "  \"rename_start_index\": " << config.transform.rename.startIndex << ",\n";
    out << "  \"rename_digits\": " << config.transform.rename.digits << ",\n";
    out << "  \"jpeg_quality\": " << config.transform.rename.jpegQuality << ",\n";
    out << "  \"output_extension\": \"" << jsonEscape(config.transform.rename.outputExtension) << "\",\n";
    out << "  \"train_ratio\": " << config.split.trainRatio << ",\n";
    out << "  \"val_ratio\": " << config.split.valRatio << ",\n";
    out << "  \"test_ratio\": " << config.split.testRatio << ",\n";
    out << "  \"split_seed\": " << config.split.seed << ",\n";
    out << "  \"include_negative\": " << (config.split.includeNegative ? "true" : "false") << ",\n";
    out << "  \"split_source_annotation_format\": \"" << annotationFormatName(config.split.sourceAnnotationFormat) << "\",\n";
    out << "  \"dataset_format\": \"" << datasetFormatName(config.split.format) << "\",\n";
    out << "  \"inference_model_path\": \"" << jsonEscape(config.inference.modelPath.string()) << "\",\n";
    out << "  \"inference_names_path\": \"" << jsonEscape(config.inference.namesPath.string()) << "\",\n";
    out << "  \"inference_class_names\": [";
    for (size_t i = 0; i < config.inference.classNames.size(); ++i) {
        if (i) out << ", ";
        out << "\"" << jsonEscape(config.inference.classNames[i]) << "\"";
    }
    out << "],\n";
    out << "  \"inference_device_policy\": \"" << devicePolicyName(config.inference.devicePolicy) << "\",\n";
    out << "  \"inference_input_width\": " << config.inference.inputWidth << ",\n";
    out << "  \"inference_input_height\": " << config.inference.inputHeight << ",\n";
    out << "  \"inference_confidence_threshold\": " << config.inference.confidenceThreshold << ",\n";
    out << "  \"inference_iou_threshold\": " << config.inference.iouThreshold << "\n";
    out << "}\n";
    return true;
}

ProjectConfig ProjectManager::load(const fs::path& path) {
    std::ifstream in(path);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    ProjectConfig config = createDefault(path);
    config.imageInputDir = stringValue(text, "image_input_dir");
    config.videoInputPath = stringValue(text, "video_input_path");
    config.annotationDir = stringValue(text, "annotation_dir");
    config.outputDir = stringValue(text, "output_dir");
    config.annotationFormat = annotationFormatValue(stringValue(text, "annotation_format"), config.annotationFormat);
    config.outputAnnotationFormat = annotationFormatValue(stringValue(text, "output_annotation_format"), config.outputAnnotationFormat);
    auto classes = stringArrayValue(text, "class_names");
    if (!classes.empty()) {
        config.classNames = classes;
        config.split.classNames = classes;
    }
    config.transform.enableResize = boolValue(text, "enable_resize", config.transform.enableResize);
    config.transform.resize.width = static_cast<int>(numberValue(text, "resize_width", config.transform.resize.width));
    config.transform.resize.height = static_cast<int>(numberValue(text, "resize_height", config.transform.resize.height));
    config.transform.resize.keepAspect = boolValue(text, "keep_aspect", config.transform.resize.keepAspect);
    config.transform.resize.paddingColor = cv::Scalar(
        numberValue(text, "padding_b", config.transform.resize.paddingColor[0]),
        numberValue(text, "padding_g", config.transform.resize.paddingColor[1]),
        numberValue(text, "padding_r", config.transform.resize.paddingColor[2])
    );
    config.transform.enableCrop = boolValue(text, "enable_crop", config.transform.enableCrop);
    config.transform.crop.x = static_cast<int>(numberValue(text, "crop_x", config.transform.crop.x));
    config.transform.crop.y = static_cast<int>(numberValue(text, "crop_y", config.transform.crop.y));
    config.transform.crop.width = static_cast<int>(numberValue(text, "crop_width", config.transform.crop.width));
    config.transform.crop.height = static_cast<int>(numberValue(text, "crop_height", config.transform.crop.height));
    config.transform.crop.keepVisibleRatio = numberValue(text, "crop_keep_visible_ratio", config.transform.crop.keepVisibleRatio);
    config.transform.enableTiling = boolValue(text, "enable_tiling", config.transform.enableTiling);
    config.transform.tile.tileWidth = static_cast<int>(numberValue(text, "tile_width", config.transform.tile.tileWidth));
    config.transform.tile.tileHeight = static_cast<int>(numberValue(text, "tile_height", config.transform.tile.tileHeight));
    config.transform.tile.overlapX = static_cast<int>(numberValue(text, "overlap_x", config.transform.tile.overlapX));
    config.transform.tile.overlapY = static_cast<int>(numberValue(text, "overlap_y", config.transform.tile.overlapY));
    config.transform.tile.padEdges = boolValue(text, "tile_pad_edges", config.transform.tile.padEdges);
    config.transform.tile.keepVisibleRatio = numberValue(text, "tile_keep_visible_ratio", config.transform.tile.keepVisibleRatio);
    config.transform.flipHorizontal = boolValue(text, "flip_horizontal", config.transform.flipHorizontal);
    config.transform.flipVertical = boolValue(text, "flip_vertical", config.transform.flipVertical);
    config.transform.rotateDegrees = static_cast<int>(numberValue(text, "rotate_degrees", config.transform.rotateDegrees));
    config.transform.enableBrightnessContrast = boolValue(text, "enable_brightness_contrast", config.transform.enableBrightnessContrast);
    config.transform.brightness = numberValue(text, "brightness", config.transform.brightness);
    config.transform.contrast = numberValue(text, "contrast", config.transform.contrast);
    const std::string prefix = stringValue(text, "rename_prefix");
    if (!prefix.empty()) config.transform.rename.prefix = prefix;
    config.transform.rename.startIndex = static_cast<int>(numberValue(text, "rename_start_index", config.transform.rename.startIndex));
    config.transform.rename.digits = static_cast<int>(numberValue(text, "rename_digits", config.transform.rename.digits));
    config.transform.rename.jpegQuality = static_cast<int>(numberValue(text, "jpeg_quality", config.transform.rename.jpegQuality));
    const std::string extension = stringValue(text, "output_extension");
    if (!extension.empty()) config.transform.rename.outputExtension = extension;
    config.split.trainRatio = numberValue(text, "train_ratio", config.split.trainRatio);
    config.split.valRatio = numberValue(text, "val_ratio", config.split.valRatio);
    config.split.testRatio = numberValue(text, "test_ratio", config.split.testRatio);
    config.split.seed = static_cast<std::uint32_t>(numberValue(text, "split_seed", config.split.seed));
    config.split.includeNegative = boolValue(text, "include_negative", config.split.includeNegative);
    config.split.sourceAnnotationFormat = annotationFormatValue(stringValue(text, "split_source_annotation_format"), config.annotationFormat);
    config.split.format = datasetFormatValue(stringValue(text, "dataset_format"), config.split.format);
    config.inference.modelPath = stringValue(text, "inference_model_path");
    config.inference.namesPath = stringValue(text, "inference_names_path");
    auto inferenceClasses = stringArrayValue(text, "inference_class_names");
    if (!inferenceClasses.empty()) {
        config.inference.classNames = inferenceClasses;
    }
    config.inference.devicePolicy = devicePolicyValue(stringValue(text, "inference_device_policy"), config.inference.devicePolicy);
    config.inference.inputWidth = static_cast<int>(numberValue(text, "inference_input_width", config.inference.inputWidth));
    config.inference.inputHeight = static_cast<int>(numberValue(text, "inference_input_height", config.inference.inputHeight));
    config.inference.confidenceThreshold = static_cast<float>(numberValue(text, "inference_confidence_threshold", config.inference.confidenceThreshold));
    config.inference.iouThreshold = static_cast<float>(numberValue(text, "inference_iou_threshold", config.inference.iouThreshold));
    if (config.outputDir.empty()) {
        config.outputDir = RuntimePaths::defaultOutputDir();
    }
    return config;
}
