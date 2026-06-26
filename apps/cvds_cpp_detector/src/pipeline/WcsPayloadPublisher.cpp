#include "pipeline/WcsPayloadPublisher.h"

#include <QDir>
#include <QFile>
#include <QFileDevice>
#include <QFileInfo>
#include <QJsonDocument>
#include <QStringList>

#include <utility>

namespace {

void setError(QString* error, const QString& message) {
    if (error) *error = message;
}

bool ensureParentDirectory(const QString& path, QString* error) {
    const QFileInfo fileInfo(path);
    const QDir parentDir = fileInfo.absoluteDir();
    if (parentDir.exists()) return true;
    if (QDir().mkpath(parentDir.absolutePath())) return true;

    setError(error, "无法创建 WCS payload 输出目录：" + parentDir.absolutePath());
    return false;
}

}  // namespace

QString CompositeWcsPayloadPublisher::name() const {
    return QStringLiteral("CompositeWcsPayloadPublisher");
}

bool CompositeWcsPayloadPublisher::publish(const QJsonObject& payload, QString* error) {
    QStringList errors;
    for (const std::unique_ptr<WcsPayloadPublisher>& publisher : publishers_) {
        if (!publisher) continue;

        QString publishError;
        if (!publisher->publish(payload, &publishError)) {
            errors.append(publisher->name() + ": " + publishError);
        }
    }

    if (!errors.isEmpty()) {
        setError(error, errors.join("; "));
        return false;
    }
    return true;
}

void CompositeWcsPayloadPublisher::addPublisher(std::unique_ptr<WcsPayloadPublisher> publisher) {
    if (publisher) publishers_.push_back(std::move(publisher));
}

bool CompositeWcsPayloadPublisher::empty() const {
    return publishers_.empty();
}

JsonlWcsPayloadPublisher::JsonlWcsPayloadPublisher(QString path)
    : path_(std::move(path)) {}

QString JsonlWcsPayloadPublisher::name() const {
    return QStringLiteral("JsonlWcsPayloadPublisher");
}

bool JsonlWcsPayloadPublisher::publish(const QJsonObject& payload, QString* error) {
    if (path_.trimmed().isEmpty()) {
        setError(error, "WCS payload JSONL 路径为空");
        return false;
    }
    if (!ensureParentDirectory(path_, error)) {
        return false;
    }

    QFile file(path_);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Append | QIODevice::Text)) {
        setError(error, "无法打开 WCS payload JSONL 文件：" + path_ + "，原因：" + file.errorString());
        return false;
    }

    const QByteArray line = QJsonDocument(payload).toJson(QJsonDocument::Compact);
    if (file.write(line) != line.size() || file.write("\n") != 1) {
        setError(error, "写入 WCS payload JSONL 文件失败：" + path_ + "，原因：" + file.errorString());
        return false;
    }

    file.flush();
    if (file.error() != QFileDevice::NoError) {
        setError(error, "刷新 WCS payload JSONL 文件失败：" + path_ + "，原因：" + file.errorString());
        return false;
    }
    return true;
}

QString JsonlWcsPayloadPublisher::path() const {
    return path_;
}
