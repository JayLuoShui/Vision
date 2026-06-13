#pragma once

#include <QByteArray>
#include <QJsonObject>
#include <QPoint>
#include <QString>
#include <QVector>

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

struct RegionConfigDocument {
    int version = 1;
    QString totalCountRegionId;
    QVector<RegionConfig> regions;
};

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
