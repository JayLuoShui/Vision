#include "utils/JsonlWriter.h"

#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>

bool JsonlWriter::begin(const QString& path, QString* errorMessage) {
    end();
    const QFileInfo info(path);
    if (!QDir().mkpath(info.absolutePath())) {
        if (errorMessage) *errorMessage = "无法创建 JSONL 输出目录：" + info.absolutePath();
        return false;
    }
    file_.setFileName(path);
    if (!file_.open(QIODevice::WriteOnly | QIODevice::Append | QIODevice::Text)) {
        if (errorMessage) *errorMessage = file_.errorString();
        return false;
    }
    return true;
}

bool JsonlWriter::append(const QJsonObject& object, QString* errorMessage) {
    if (!file_.isOpen()) {
        if (errorMessage) *errorMessage = "JSONL 文件尚未打开";
        return false;
    }
    QByteArray line = QJsonDocument(object).toJson(QJsonDocument::Compact);
    line.append('\n');
    if (file_.write(line) != line.size() || !file_.flush()) {
        if (errorMessage) *errorMessage = file_.errorString();
        return false;
    }
    return true;
}

void JsonlWriter::end() {
    if (file_.isOpen()) file_.close();
}
