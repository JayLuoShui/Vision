#pragma once

#include <QJsonObject>
#include <QString>

#include <memory>
#include <vector>

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
