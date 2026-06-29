#pragma once

#include <QJsonObject>
#include <QString>

#include <memory>
#include <vector>

// 维护说明：WCS 发布配置目前只打开本地 JSONL 旁路；TCP 发送由 WcsTcpClient 负责。
struct WcsPublisherConfig {
    bool jsonlEnabled = false;
    QString jsonlPath;
};

// 维护说明：WcsPayloadPublisher 是发布出口接口。
// VideoPipeline 只依赖该接口，避免把具体发布方式写进检测循环。
class WcsPayloadPublisher {
public:
    virtual ~WcsPayloadPublisher() = default;

    virtual QString name() const = 0;
    virtual bool publish(const QJsonObject& payload, QString* error) = 0;
};

class CompositeWcsPayloadPublisher final : public WcsPayloadPublisher {
public:
    QString name() const override;
    bool publish(const QJsonObject& payload, QString* error) override;

    void addPublisher(std::unique_ptr<WcsPayloadPublisher> publisher);
    bool empty() const;

private:
    std::vector<std::unique_ptr<WcsPayloadPublisher>> publishers_;
};

class JsonlWcsPayloadPublisher final : public WcsPayloadPublisher {
public:
    explicit JsonlWcsPayloadPublisher(QString path);

    QString name() const override;
    bool publish(const QJsonObject& payload, QString* error) override;
    QString path() const;

private:
    QString path_;
};
