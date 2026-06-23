#pragma once

#include <QJsonObject>
#include <QString>

class JsonlWriter {
public:
    bool begin(const QString& path, QString* errorMessage = nullptr);
    bool append(const QJsonObject& object, QString* errorMessage = nullptr);
    void end();
};
