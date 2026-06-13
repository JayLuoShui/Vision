#include "RegionConfig.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonParseError>
#include <QSaveFile>
#include <QStringList>

#include <cmath>
#include <limits>
#include <stdexcept>

namespace {

std::runtime_error configError(const QString& message) {
    // 这里保持显式 throw std::runtime_error 的错误语义。
    return std::runtime_error(message.toUtf8().constData());
}

QJsonObject requireObject(const QJsonDocument& document) {
    if (!document.isObject()) {
        throw configError("区域配置根节点必须是 JSON 对象。");
    }
    return document.object();
}

QString requireString(const QJsonObject& object, const char* key, const QString& message) {
    const QJsonValue value = object.value(QLatin1String(key));
    if (!value.isString()) {
        throw configError(message);
    }
    const QString text = value.toString().trimmed();
    if (text.isEmpty()) {
        throw configError(message);
    }
    return text;
}

bool requireBool(const QJsonObject& object, const char* key, const QString& message) {
    const QJsonValue value = object.value(QLatin1String(key));
    if (!value.isBool()) {
        throw configError(message);
    }
    return value.toBool();
}

int requireInt(const QJsonObject& object, const char* key, const QString& message) {
    const QJsonValue value = object.value(QLatin1String(key));
    const double number = value.toDouble();
    if (!value.isDouble()
        || std::floor(number) != number
        || number < static_cast<double>(std::numeric_limits<int>::min())
        || number > static_cast<double>(std::numeric_limits<int>::max())) {
        throw configError(message);
    }
    return static_cast<int>(number);
}

double readDouble(const QJsonObject& object, const char* key, double defaultValue) {
    const QJsonValue value = object.value(QLatin1String(key));
    return value.isDouble() ? value.toDouble(defaultValue) : defaultValue;
}

QVector<QPoint> parsePolygonArray(const QJsonArray& array, const QString& regionId) {
    if (array.size() < 3) {
        throw configError("区域 polygon 至少需要 3 个点：" + regionId);
    }
    QVector<QPoint> polygon;
    polygon.reserve(array.size());
    for (const QJsonValue& value : array) {
        if (!value.isArray()) {
            throw configError("区域 polygon 点格式错误：" + regionId);
        }
        const QJsonArray pointArray = value.toArray();
        const double x = pointArray.size() == 2 ? pointArray[0].toDouble() : 0.0;
        const double y = pointArray.size() == 2 ? pointArray[1].toDouble() : 0.0;
        if (pointArray.size() != 2 || !pointArray[0].isDouble() || !pointArray[1].isDouble()
            || std::floor(x) != x || std::floor(y) != y
            || x < static_cast<double>(std::numeric_limits<int>::min())
            || x > static_cast<double>(std::numeric_limits<int>::max())
            || y < static_cast<double>(std::numeric_limits<int>::min())
            || y > static_cast<double>(std::numeric_limits<int>::max())) {
            throw configError("区域 polygon 点格式错误：" + regionId);
        }
        polygon.push_back(QPoint(static_cast<int>(x), static_cast<int>(y)));
    }
    return polygon;
}

QJsonArray polygonToJsonArray(const QVector<QPoint>& polygon) {
    QJsonArray array;
    for (const QPoint& point : polygon) {
        array.push_back(QJsonArray{point.x(), point.y()});
    }
    return array;
}

RegionConfig regionConfigFromJson(const QJsonObject& object) {
    RegionConfig config;
    config.id = requireString(object, "id", "区域 id 不能为空。");
    config.name = requireString(object, "name", "区域 name 不能为空：" + config.id);
    const QJsonValue polygonValue = object.value("polygon");
    if (!polygonValue.isArray()) {
        throw configError("区域配置缺少 polygon：" + config.id);
    }
    config.polygon = parsePolygonArray(polygonValue.toArray(), config.id);
    config.polygonClosed = true;
    config.countEnabled = requireBool(object, "count_enabled", "区域 count_enabled 必须是布尔值：" + config.id);
    config.jamEnabled = requireBool(object, "jam_enabled", "区域 jam_enabled 必须是布尔值：" + config.id);
    config.jamSeconds = requireInt(object, "jam_seconds", "区域 jam_seconds 必须是整数：" + config.id);
    if (config.jamSeconds < 1) {
        throw configError("区域 jam_seconds 必须大于等于 1：" + config.id);
    }
    config.priority = requireInt(object, "priority", "区域 priority 必须是整数：" + config.id);
    return config;
}

QJsonObject regionConfigToJson(const RegionConfig& config) {
    QJsonObject object;
    object.insert("id", config.id);
    object.insert("name", config.name);
    object.insert("polygon", polygonToJsonArray(config.polygon));
    object.insert("count_enabled", config.countEnabled);
    object.insert("jam_enabled", config.jamEnabled);
    object.insert("jam_seconds", config.jamSeconds);
    object.insert("priority", config.priority);
    return object;
}

void validateDocument(const RegionConfigDocument& document) {
    if (document.regions.isEmpty()) {
        throw configError("区域配置缺少 regions。");
    }
    if (document.totalCountRegionId.trimmed().isEmpty()) {
        throw configError("主统计区域不能为空。");
    }

    QStringList ids;
    for (const RegionConfig& config : document.regions) {
        if (config.id.trimmed().isEmpty()) {
            throw configError("区域 id 不能为空。");
        }
        if (ids.contains(config.id)) {
            throw configError("区域 id 重复：" + config.id);
        }
        ids.push_back(config.id);
        if (config.name.trimmed().isEmpty()) {
            throw configError("区域名称不能为空：" + config.id);
        }
        if (!config.polygonClosed || config.polygon.size() < 3) {
            throw configError("区域 polygon 至少需要 3 个点：" + config.id);
        }
        if (config.jamSeconds < 1) {
            throw configError("区域 jam_seconds 必须大于等于 1：" + config.id);
        }
    }
    if (!ids.contains(document.totalCountRegionId)) {
        throw configError("主统计区域不存在：" + document.totalCountRegionId);
    }
    for (const RegionConfig& config : document.regions) {
        if (config.id == document.totalCountRegionId && !config.countEnabled) {
            throw configError("主统计区域必须开启计数：" + document.totalCountRegionId);
        }
    }
}

}  // namespace

QByteArray regionConfigDocumentToJson(const RegionConfigDocument& document) {
    validateDocument(document);

    QJsonArray regionsArray;
    for (const RegionConfig& region : document.regions) {
        regionsArray.push_back(regionConfigToJson(region));
    }

    QJsonObject root;
    root.insert("version", document.version);
    root.insert("total_count_region", document.totalCountRegionId);
    root.insert("regions", regionsArray);
    return QJsonDocument(root).toJson(QJsonDocument::Indented);
}

RegionConfigDocument regionConfigDocumentFromJson(const QByteArray& jsonBytes) {
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(jsonBytes, &parseError);
    if (parseError.error != QJsonParseError::NoError) {
        throw configError("区域配置 JSON 解析失败：" + parseError.errorString());
    }
    const QJsonObject root = requireObject(document);
    const QJsonValue versionValue = root.value("version");
    if (!versionValue.isDouble()) {
        throw configError("区域配置缺少 version。");
    }
    if (std::floor(versionValue.toDouble()) != versionValue.toDouble() || versionValue.toInt() != 1) {
        throw configError("区域配置仅支持 version=1。");
    }
    const QJsonValue totalCountRegionValue = root.value("total_count_region");
    if (!totalCountRegionValue.isString() || totalCountRegionValue.toString().trimmed().isEmpty()) {
        throw configError("区域配置缺少 total_count_region。");
    }
    const QJsonValue regionsValue = root.value("regions");
    if (!regionsValue.isArray()) {
        throw configError("区域配置缺少 regions。");
    }

    RegionConfigDocument regionDocument;
    regionDocument.version = versionValue.toInt(1);
    regionDocument.totalCountRegionId = totalCountRegionValue.toString().trimmed();

    const QJsonArray regionsArray = regionsValue.toArray();
    regionDocument.regions.reserve(regionsArray.size());
    for (const QJsonValue& value : regionsArray) {
        if (!value.isObject()) {
            throw configError("区域配置中的 region 必须是对象。");
        }
        regionDocument.regions.push_back(regionConfigFromJson(value.toObject()));
    }

    validateDocument(regionDocument);
    return regionDocument;
}

RegionConfigDocument loadRegionConfigDocument(const QString& path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        throw configError("无法读取区域配置文件：" + path);
    }
    return regionConfigDocumentFromJson(file.readAll());
}

void saveRegionConfigDocument(const QString& path, const RegionConfigDocument& document) {
    const QFileInfo fileInfo(path);
    if (!QDir().mkpath(fileInfo.absolutePath())) {
        throw configError("无法创建区域配置目录：" + fileInfo.absolutePath());
    }
    QSaveFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        throw configError("无法写入区域配置文件：" + path);
    }
    const QByteArray jsonBytes = regionConfigDocumentToJson(document);
    if (file.write(jsonBytes) != jsonBytes.size()) {
        throw configError("区域配置写入不完整：" + path);
    }
    if (!file.commit()) {
        throw configError("无法提交区域配置文件：" + path);
    }
}

QJsonObject regionRuntimeStateToJson(const RegionRuntimeState& state) {
    QJsonObject object;
    object.insert("id", state.id);
    object.insert("name", state.name);
    object.insert("status", state.status);
    object.insert("signal", state.signal);
    object.insert("event_type", state.eventType);
    object.insert("flow_count", state.flowCount);
    object.insert("inside_count", state.insideCount);
    object.insert("jam_count", state.jamCount);
    object.insert("max_inside_count", state.maxInsideCount);
    object.insert("jam_active", state.jamActive);
    object.insert("stale_seconds", state.staleSeconds);
    return object;
}

RegionRuntimeState regionRuntimeStateFromJson(const QJsonObject& object) {
    RegionRuntimeState state;
    state.id = object.value("id").toString().trimmed();
    state.name = object.value("name").toString().trimmed();
    state.status = object.value("status").toString().trimmed();
    state.signal = object.value("signal").toString().trimmed();
    state.eventType = object.value("event_type").toString().trimmed();
    state.flowCount = object.value("flow_count").toInt();
    state.insideCount = object.value("inside_count").toInt();
    state.jamCount = object.value("jam_count").toInt();
    state.maxInsideCount = object.value("max_inside_count").toInt();
    state.jamActive = object.value("jam_active").toBool();
    state.staleSeconds = readDouble(object, "stale_seconds", 0.0);
    return state;
}

QString polygonToText(const QVector<QPoint>& polygon) {
    QStringList parts;
    parts.reserve(polygon.size() * 2);
    for (const QPoint& point : polygon) {
        parts.push_back(QString::number(point.x()));
        parts.push_back(QString::number(point.y()));
    }
    return parts.join(",");
}

QVector<QPoint> polygonFromText(const QString& text, const QString& label, bool allowEmpty) {
    const QString trimmed = text.trimmed();
    if (trimmed.isEmpty()) {
        if (allowEmpty) {
            return {};
        }
        throw configError(label + "不能为空。");
    }
    const QStringList parts = trimmed.split(",", Qt::SkipEmptyParts);
    if (parts.size() < 6 || parts.size() % 2 != 0) {
        throw configError(label + "至少需要 3 个点，格式为 x1,y1,x2,y2,...");
    }
    QVector<QPoint> polygon;
    polygon.reserve(parts.size() / 2);
    for (int i = 0; i + 1 < parts.size(); i += 2) {
        bool okX = false;
        bool okY = false;
        const int x = parts[i].trimmed().toInt(&okX);
        const int y = parts[i + 1].trimmed().toInt(&okY);
        if (!okX || !okY) {
            throw configError(label + "存在非法坐标。");
        }
        polygon.push_back(QPoint(x, y));
    }
    return polygon;
}
