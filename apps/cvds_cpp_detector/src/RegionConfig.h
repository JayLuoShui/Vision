#pragma once

#include <QByteArray>
#include <QJsonObject>
#include <QPoint>
#include <QString>
#include <QVector>

// 维护说明：RegionConfig 是界面、检测管线和输出文件之间共享的 ROI 配置。
// 不要在读取配置时静默修复非法区域；应在保存或启动前明确报错。
struct RegionConfig {
    QString id;
    QString name;
    QVector<QPoint> polygon;
    bool polygonClosed = false;
    bool countEnabled = true;
    bool jamEnabled = true;
    int jamSeconds = 5;
    int priority = 0;
};

// 维护说明：totalCountRegionId 决定顶部 KPI 的累计口径，可以是单个区域或多区域汇总。
struct RegionConfigDocument {
    int version = 1;
    QString totalCountRegionId;
    QVector<RegionConfig> regions;
};

// 维护说明：RegionRuntimeState 是每帧对外展示和写文件的区域状态，不保存长期配置。
struct RegionRuntimeState {
    QString id;
    QString name;
    QString status;
    QString signal;
    QString eventType;
    int flowCount = 0;
    int insideCount = 0;
    int jamCount = 0;
    int maxInsideCount = 0;
    bool jamActive = false;
    double staleSeconds = 0.0;
};

QByteArray regionConfigDocumentToJson(const RegionConfigDocument& document);
RegionConfigDocument regionConfigDocumentFromJson(const QByteArray& jsonBytes);
RegionConfigDocument loadRegionConfigDocument(const QString& path);
void saveRegionConfigDocument(const QString& path, const RegionConfigDocument& document);

QJsonObject regionRuntimeStateToJson(const RegionRuntimeState& state);
RegionRuntimeState regionRuntimeStateFromJson(const QJsonObject& object);

QString polygonToText(const QVector<QPoint>& polygon);
QVector<QPoint> polygonFromText(const QString& text, const QString& label, bool allowEmpty = false);
