#pragma once

#include "WcsConfig.h"
#include "WcsMessage.h"

#include <QObject>
#include <QQueue>
#include <QTcpSocket>
#include <QTimer>

class WcsTcpClient : public QObject {
    Q_OBJECT

public:
    explicit WcsTcpClient(QObject* parent = nullptr);

    void configure(const WcsEndpointConfig& config);
    bool isConnected() const;
    QString stateText() const;

public slots:
    void start();
    void stop();
    void sendMessage(const QJsonObject& object);
    void sendCameraStatus(const CameraRuntimeSnapshot& snapshot);
    void sendFlowUpdate(const WcsFlowUpdate& update);
    void sendJamOn(const WcsJamEvent& event);
    void sendJamOff(const WcsJamEvent& event);
    void sendErrorEvent(const QString& cameraId, const QString& code, const QString& message);
    void sendHeartbeat(int cameraOnline, int cameraTotal, double gpuUsagePercent);

signals:
    void connected();
    void disconnected();
    void stateChanged(const QString& state);
    void errorOccurred(const QString& error);
    void messageSent(const QByteArray& payload);
    void messageDropped(const QString& reason);

private slots:
    void connectToServer();
    void flushQueue();
    void handleConnected();
    void handleDisconnected();
    void handleSocketError(QAbstractSocket::SocketError error);

private:
    void scheduleReconnect();
    void enqueuePayload(const QByteArray& payload);

    WcsEndpointConfig config_;
    QTcpSocket* socket_ = nullptr;
    QTimer reconnectTimer_;
    QQueue<QByteArray> pendingPayloads_;
    bool running_ = false;
    int maxPendingMessages_ = 1000;
};
