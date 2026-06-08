#include "core/AnnotationIO.h"

#include <opencv2/imgcodecs.hpp>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <regex>
#include <sstream>
#include <unordered_map>

namespace fs = std::filesystem;

namespace {

std::string readAll(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        return {};
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

void ensureParent(const fs::path& path) {
    if (!path.parent_path().empty()) {
        fs::create_directories(path.parent_path());
    }
}

std::vector<double> parseNumbers(const std::string& line) {
    std::string clean = line;
    if (clean.size() >= 3 &&
        static_cast<unsigned char>(clean[0]) == 0xEF &&
        static_cast<unsigned char>(clean[1]) == 0xBB &&
        static_cast<unsigned char>(clean[2]) == 0xBF) {
        clean.erase(0, 3);
    }
    std::istringstream ss(clean);
    std::vector<double> values;
    double value = 0;
    while (ss >> value) {
        values.push_back(value);
    }
    return values;
}

std::string xmlEscape(std::string text) {
    std::string out;
    for (char ch : text) {
        if (ch == '&') out += "&amp;";
        else if (ch == '<') out += "&lt;";
        else if (ch == '>') out += "&gt;";
        else out += ch;
    }
    return out;
}

std::string firstMatch(const std::string& text, const std::regex& pattern) {
    std::smatch match;
    if (std::regex_search(text, match, pattern) && match.size() > 1) {
        return match[1].str();
    }
    return {};
}

int classIdFromName(const std::string& name, const std::vector<std::string>& classNames) {
    auto it = std::find(classNames.begin(), classNames.end(), name);
    return it == classNames.end() ? -1 : static_cast<int>(std::distance(classNames.begin(), it));
}

bool isNormalized(double value) {
    return std::isfinite(value) && value >= 0.0 && value <= 1.0;
}

bool isValidYoloClass(double value) {
    return std::isfinite(value) && value >= 0.0 && std::floor(value) == value;
}

bool isValidYoloBox(const std::vector<double>& values) {
    if (values.size() != 5 || !isValidYoloClass(values[0])) {
        return false;
    }
    if (!isNormalized(values[1]) || !isNormalized(values[2]) || !isNormalized(values[3]) || !isNormalized(values[4])) {
        return false;
    }
    if (values[3] <= 0.0 || values[4] <= 0.0) {
        return false;
    }
    return values[1] - values[3] / 2.0 >= 0.0 &&
        values[2] - values[4] / 2.0 >= 0.0 &&
        values[1] + values[3] / 2.0 <= 1.0 &&
        values[2] + values[4] / 2.0 <= 1.0;
}

bool isValidYoloPolygon(const std::vector<double>& values) {
    if (values.size() < 7 || values.size() % 2 != 1 || !isValidYoloClass(values[0])) {
        return false;
    }
    for (size_t i = 1; i < values.size(); ++i) {
        if (!isNormalized(values[i])) {
            return false;
        }
    }
    return true;
}

std::string classNameFromId(int id, const std::vector<std::string>& classNames) {
    if (id >= 0 && id < static_cast<int>(classNames.size())) {
        return classNames[id];
    }
    return std::to_string(id);
}

std::vector<std::string> splitObjects(const std::string& text, const std::string& key) {
    std::vector<std::string> objects;
    std::regex objectPattern("\\{[^\\{\\}]*\"" + key + "\"[^\\{\\}]*\\}");
    for (std::sregex_iterator it(text.begin(), text.end(), objectPattern), end; it != end; ++it) {
        objects.push_back(it->str());
    }
    return objects;
}

double jsonNumber(const std::string& object, const std::string& key, double fallback = 0.0) {
    const std::string value = firstMatch(object, std::regex("\"" + key + "\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?)"));
    return value.empty() ? fallback : std::stod(value);
}

std::string jsonString(const std::string& object, const std::string& key) {
    return firstMatch(object, std::regex("\"" + key + "\"\\s*:\\s*\"([^\"]*)\""));
}

std::vector<double> jsonArrayNumbers(const std::string& object, const std::string& key) {
    const std::string body = firstMatch(object, std::regex("\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]"));
    std::vector<double> values;
    std::regex numberPattern("-?[0-9]+(?:\\.[0-9]+)?");
    for (std::sregex_iterator it(body.begin(), body.end(), numberPattern), end; it != end; ++it) {
        values.push_back(std::stod(it->str()));
    }
    return values;
}

std::unordered_map<int, int> cocoCategoryMap(const std::string& json, const std::vector<std::string>& classNames) {
    std::unordered_map<int, int> idToClass;
    std::vector<std::pair<int, std::string>> categories;
    for (const auto& item : splitObjects(json, "name")) {
        const int categoryId = static_cast<int>(jsonNumber(item, "id", -1));
        const std::string name = jsonString(item, "name");
        if (categoryId >= 0 && !name.empty()) {
            categories.push_back({categoryId, name});
        }
    }
    for (size_t i = 0; i < categories.size(); ++i) {
        const int byName = classIdFromName(categories[i].second, classNames);
        idToClass[categories[i].first] = byName >= 0 ? byName : static_cast<int>(i);
    }
    return idToClass;
}

void updateBoxFromPolygon(AnnotationObject& obj) {
    if (!obj.hasPolygon || obj.polygons.empty() || obj.polygons.front().points.empty()) {
        return;
    }
    const auto& points = obj.polygons.front().points;
    double minX = points.front().x;
    double minY = points.front().y;
    double maxX = minX;
    double maxY = minY;
    for (const auto& point : points) {
        minX = std::min(minX, point.x);
        minY = std::min(minY, point.y);
        maxX = std::max(maxX, point.x);
        maxY = std::max(maxY, point.y);
    }
    obj.box = {minX, minY, maxX, maxY};
}

}  // namespace

ImageAnnotation AnnotationIO::loadYolo(const fs::path& labelPath, const fs::path& imagePath, int width, int height, const std::vector<std::string>& classNames) {
    ImageAnnotation ann;
    ann.imagePath = imagePath;
    ann.width = width;
    ann.height = height;
    std::ifstream in(labelPath);
    std::string line;
    while (std::getline(in, line)) {
        auto values = parseNumbers(line);
        if (isValidYoloBox(values)) {
            AnnotationObject obj;
            obj.classId = static_cast<int>(values[0]);
            obj.className = classNameFromId(obj.classId, classNames);
            const double cx = values[1] * width;
            const double cy = values[2] * height;
            const double bw = values[3] * width;
            const double bh = values[4] * height;
            obj.box = {cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2};
            ann.objects.push_back(obj);
        } else if (isValidYoloPolygon(values)) {
            AnnotationObject obj;
            obj.classId = static_cast<int>(values[0]);
            obj.className = classNameFromId(obj.classId, classNames);
            Polygon polygon;
            for (size_t i = 1; i + 1 < values.size(); i += 2) {
                polygon.points.push_back({values[i] * width, values[i + 1] * height});
            }
            obj.polygons.push_back(polygon);
            obj.hasPolygon = true;
            double minX = polygon.points.front().x;
            double minY = polygon.points.front().y;
            double maxX = minX;
            double maxY = minY;
            for (const auto& point : polygon.points) {
                minX = std::min(minX, point.x);
                minY = std::min(minY, point.y);
                maxX = std::max(maxX, point.x);
                maxY = std::max(maxY, point.y);
            }
            obj.box = {minX, minY, maxX, maxY};
            ann.objects.push_back(obj);
        }
    }
    return ann;
}

void AnnotationIO::saveYolo(const ImageAnnotation& annotation, const fs::path& labelPath, const std::vector<std::string>&, bool preferSegment) {
    ensureParent(labelPath);
    std::ofstream out(labelPath);
    out << std::fixed << std::setprecision(8);
    for (const auto& obj : annotation.objects) {
        if (preferSegment && obj.hasPolygon && !obj.polygons.empty()) {
            out << obj.classId;
            for (const auto& point : obj.polygons.front().points) {
                out << ' ' << point.x / annotation.width << ' ' << point.y / annotation.height;
            }
            out << '\n';
        } else {
            const double cx = (obj.box.x1 + obj.box.x2) / 2.0 / annotation.width;
            const double cy = (obj.box.y1 + obj.box.y2) / 2.0 / annotation.height;
            const double bw = (obj.box.x2 - obj.box.x1) / annotation.width;
            const double bh = (obj.box.y2 - obj.box.y1) / annotation.height;
            out << obj.classId << ' ' << cx << ' ' << cy << ' ' << bw << ' ' << bh << '\n';
        }
    }
}

ImageAnnotation AnnotationIO::loadVoc(const fs::path& xmlPath, const std::vector<std::string>& classNames) {
    const std::string xml = readAll(xmlPath);
    ImageAnnotation ann;
    ann.imagePath = xmlPath.parent_path() / firstMatch(xml, std::regex("<filename>([^<]+)</filename>"));
    ann.width = std::stoi(firstMatch(xml, std::regex("<width>([0-9]+)</width>")));
    ann.height = std::stoi(firstMatch(xml, std::regex("<height>([0-9]+)</height>")));
    std::regex objectPattern("<object>([\\s\\S]*?)</object>");
    for (std::sregex_iterator it(xml.begin(), xml.end(), objectPattern), end; it != end; ++it) {
        const std::string block = (*it)[1].str();
        AnnotationObject obj;
        obj.className = firstMatch(block, std::regex("<name>([^<]+)</name>"));
        obj.classId = classIdFromName(obj.className, classNames);
        obj.box = {
            std::stod(firstMatch(block, std::regex("<xmin>([^<]+)</xmin>"))),
            std::stod(firstMatch(block, std::regex("<ymin>([^<]+)</ymin>"))),
            std::stod(firstMatch(block, std::regex("<xmax>([^<]+)</xmax>"))),
            std::stod(firstMatch(block, std::regex("<ymax>([^<]+)</ymax>")))
        };
        ann.objects.push_back(obj);
    }
    return ann;
}

void AnnotationIO::saveVoc(const ImageAnnotation& annotation, const fs::path& xmlPath) {
    ensureParent(xmlPath);
    std::ofstream out(xmlPath);
    out << "<annotation>\n";
    out << "  <filename>" << xmlEscape(annotation.imagePath.filename().string()) << "</filename>\n";
    out << "  <size><width>" << annotation.width << "</width><height>" << annotation.height << "</height><depth>3</depth></size>\n";
    for (const auto& obj : annotation.objects) {
        out << "  <object><name>" << xmlEscape(obj.className) << "</name><bndbox>"
            << "<xmin>" << static_cast<int>(std::round(obj.box.x1)) << "</xmin>"
            << "<ymin>" << static_cast<int>(std::round(obj.box.y1)) << "</ymin>"
            << "<xmax>" << static_cast<int>(std::round(obj.box.x2)) << "</xmax>"
            << "<ymax>" << static_cast<int>(std::round(obj.box.y2)) << "</ymax>"
            << "</bndbox></object>\n";
    }
    out << "</annotation>\n";
}

std::vector<ImageAnnotation> AnnotationIO::loadCoco(const fs::path& jsonPath, const std::vector<std::string>& classNames) {
    const std::string json = readAll(jsonPath);
    std::unordered_map<int, ImageAnnotation> byId;
    const auto categoryMap = cocoCategoryMap(json, classNames);
    for (const auto& item : splitObjects(json, "file_name")) {
        const int id = static_cast<int>(jsonNumber(item, "id"));
        ImageAnnotation ann;
        ann.imagePath = jsonString(item, "file_name");
        ann.width = static_cast<int>(jsonNumber(item, "width"));
        ann.height = static_cast<int>(jsonNumber(item, "height"));
        byId[id] = ann;
    }
    for (const auto& item : splitObjects(json, "image_id")) {
        const int imageId = static_cast<int>(jsonNumber(item, "image_id"));
        auto found = byId.find(imageId);
        if (found == byId.end()) {
            continue;
        }
        AnnotationObject obj;
        const int categoryId = static_cast<int>(jsonNumber(item, "category_id"));
        auto mappedClass = categoryMap.find(categoryId);
        obj.classId = mappedClass == categoryMap.end() ? categoryId - 1 : mappedClass->second;
        obj.className = classNameFromId(obj.classId, classNames);
        auto bbox = jsonArrayNumbers(item, "bbox");
        if (bbox.size() >= 4) {
            obj.box = {bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]};
        }
        auto segmentation = jsonArrayNumbers(item, "segmentation");
        if (segmentation.size() >= 6 && segmentation.size() % 2 == 0) {
            Polygon polygon;
            for (size_t i = 0; i + 1 < segmentation.size(); i += 2) {
                polygon.points.push_back({segmentation[i], segmentation[i + 1]});
            }
            obj.polygons.push_back(polygon);
            obj.hasPolygon = true;
            if (bbox.size() < 4) {
                updateBoxFromPolygon(obj);
            }
        }
        found->second.objects.push_back(obj);
    }
    std::vector<ImageAnnotation> output;
    for (auto& [_, ann] : byId) {
        output.push_back(ann);
    }
    return output;
}

void AnnotationIO::saveCoco(const std::vector<ImageAnnotation>& annotations, const fs::path& jsonPath, const std::vector<std::string>& classNames) {
    ensureParent(jsonPath);
    std::ofstream out(jsonPath);
    out << "{\n\"images\":[";
    for (size_t i = 0; i < annotations.size(); ++i) {
        if (i) out << ',';
        out << "{\"id\":" << (i + 1) << ",\"file_name\":\"" << annotations[i].imagePath.filename().string()
            << "\",\"width\":" << annotations[i].width << ",\"height\":" << annotations[i].height << "}";
    }
    out << "],\n\"annotations\":[";
    int annId = 1;
    bool first = true;
    for (size_t imageIndex = 0; imageIndex < annotations.size(); ++imageIndex) {
        for (const auto& obj : annotations[imageIndex].objects) {
            if (!first) out << ',';
            first = false;
            const double w = obj.box.x2 - obj.box.x1;
            const double h = obj.box.y2 - obj.box.y1;
            out << "{\"id\":" << annId++ << ",\"image_id\":" << (imageIndex + 1) << ",\"category_id\":" << (obj.classId + 1)
                << ",\"bbox\":[" << obj.box.x1 << ',' << obj.box.y1 << ',' << w << ',' << h << "]";
            if (obj.hasPolygon && !obj.polygons.empty() && obj.polygons.front().points.size() >= 3) {
                out << ",\"segmentation\":[[";
                const auto& points = obj.polygons.front().points;
                for (size_t i = 0; i < points.size(); ++i) {
                    if (i) {
                        out << ',';
                    }
                    out << points[i].x << ',' << points[i].y;
                }
                out << "]]";
            } else {
                out << ",\"segmentation\":[]";
            }
            out << ",\"area\":" << (w * h) << ",\"iscrowd\":0}";
        }
    }
    out << "],\n\"categories\":[";
    for (size_t i = 0; i < classNames.size(); ++i) {
        if (i) out << ',';
        out << "{\"id\":" << (i + 1) << ",\"name\":\"" << classNames[i] << "\"}";
    }
    out << "]\n}\n";
}

cv::Mat AnnotationIO::loadMaskPng(const fs::path& maskPath) {
    return cv::imread(maskPath.string(), cv::IMREAD_UNCHANGED);
}

void AnnotationIO::saveMaskPng(const cv::Mat& mask, const fs::path& maskPath, const fs::path& sidecarPath, const std::vector<std::string>& classNames) {
    ensureParent(maskPath);
    cv::imwrite(maskPath.string(), mask);
    ensureParent(sidecarPath);
    std::ofstream out(sidecarPath);
    out << "{\"classes\":[";
    for (size_t i = 0; i < classNames.size(); ++i) {
        if (i) out << ',';
        out << "{\"id\":" << i << ",\"name\":\"" << classNames[i] << "\"}";
    }
    out << "]}\n";
}
