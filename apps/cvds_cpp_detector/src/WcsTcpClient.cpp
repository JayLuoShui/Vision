#include "WcsTcpClient.h"

#include <QAbstractSocket>

WcsTcpClient::WcsTcpClient(QObject* parent)
    : QObject(parent), socket_(new QTcpSocket(this)) {
    reconnectTimer_.setSingleShot(true);
    connect(&reconnectTimer_, &QTimer::timeout, this, &WcsTcpClient::connectToServer);
    connect(socket_, &QTcpSocket::connected, this, &WcsTcpClient::handleConnected);
    connect(socket_, &QTcpSocket::disconnected, this, &WcsTcpClient::handleDisconnected);
    connect(socket_, &QTcpSocket::bytesWritten, this, &WcsTcpClient::flushQueue);
    connect(socket_, &QTcpSocket::errorOccurred, this, &WcsTcpClient::handleSocketError);
}

void WcsTcpClient::configure(const WcsEndpointConfig& config) {
    const bool shouldRestart = running_;
    if (shouldRestart) {
        stop();
    }
    config_ = config;
    if (shouldRestart) {
        start();
    }
}

bool WcsTcpClient::isConnected() const {
    return socket_ != nullptr && socket_->state() == QAbstractSocket::ConnectedState;
}

QString WcsTcpClient::stateText() const {
    if (!config_.enabled) {
        return "WCS 未启用";
    }
    if (!running_) {
        return "WCS 已停止";
    }
    switch (socket_->state()) {
    case QAbstractSocket::ConnectedState:
        return "WCS 已连接";
    case QAbstractSocket::ConnectingState:
        return "WCS 连接中";
    default:
        return "WCS 未连接";
    }
}

void WcsTcpClient::start() {
    if (!config_.enabled || running_) {
        return;
    }
    running_ = true;
    emit stateChanged(stateText());
    connectToServer();
}

void WcsTcpClient::stop() {
    running_ = false;
    reconnectTimer_.stop();
    pendingPayloads_.clear();
    if (socket_ != nullptr) {
        socket_->abort();
    }
    emit stateChanged(stateText());
}

void WcsTcpClient::sendMessage(const QJsonObject& object) {
    if (!running_ || !config_.enabled) {
        emit messageDropped("WCS 未启用或未启动");
        return;
    }
    enqueuePayload(encodeWcsMessage(object, config_.newlineDelimitedJson));
}

void WcsTcpClient::sendCameraStatus(const CameraRuntimeSnapshot& snapshot) {
    sendMessage(buildWcsCameraStatusMessage(config_.deviceId, snapshot));
}

void WcsTcpClient::sendFlowUpdate(const WcsFlowUpdate& update) {
    sendMessage(buildWcsFlowUpdateMessage(config_.deviceId, update));
}

void WcsTcpClient::sendJamOn(const WcsJamEvent& event) {
    sendMessage(buildWcsJamOnMessage(config_.deviceId, event));
}

void WcsTcpClient::sendJamOff(const WcsJamEvent& event) {
    sendMessage(buildWcsJamOffMessage(config_.deviceId, event));
}

void WcsTcpClient::sendErrorEvent(const QString& cameraId, const QString& code, const QString& message) {
    sendMessage(buildWcsErrorMessage(config_.deviceId, cameraId, code, message));
}

void WcsTcpClient::sendHeartbeat(int cameraOnline, int cameraTotal, double gpuUsagePercent) {
    sendMessage(buildWcsHeartbeatMessage(config_.deviceId, cameraOnline, cameraTotal, gpuUsagePercent));
}

void WcsTcpClient::connectToServer() {
    if (!running_ || !config_.enabled || socket_ == nullptr) {
        return;
    }
    if (socket_->state() == QAbstractSocket::ConnectedState || socket_->state() == QAbstractSocket::ConnectingState) {
        return;
    }
    socket_->connectToHost(config_.host, config_.port);
    emit stateChanged(stateText());
}

void WcsTcpClient::flushQueue() {
    if (!isConnected()) {
        return;
    }
    while (!pendingPayloads_.isEmpty() && socket_->bytesToWrite() < 1024 * 1024) {
        const QByteArray payload = pendingPayloads_.dequeue();
        const qint64 written = socket_->write(payload);
        if (written != payload.size()) {
            emit messageDropped("WCS socket 写入不完整");
            break;
        }
        emit messageSent(payload);
    }
}

void WcsTcpClient::handleConnected() {
    emit connected();
    emit stateChanged(stateText());
    flushQueue();
}

void WcsTcpClient::handleDisconnected() {
    emit disconnected();
    emit stateChanged(stateText());
    scheduleReconnect();
}

void WcsTcpClient::handleSocketError(QAbstractSocket::SocketError error) {
    Q_UNUSED(error);
    if (!running_) {
        return;
    }
    emit errorOccurred(socket_->errorString());
    emit stateChanged(stateText());
    scheduleReconnect();
}

void WcsTcpClient::scheduleReconnect() {
    if (!running_ || !config_.enabled || reconnectTimer_.isActive()) {
        return;
    }
    reconnectTimer_.start(config_.reconnectMs);
}

void WcsTcpClient::enqueuePayload(const QByteArray& payload) {
    if (pendingPayloads_.size() >= maxPendingMessages_) {
        pendingPayloads_.dequeue();
        emit messageDropped("WCS 待发送队列已满，丢弃最旧消息");
    }
    pendingPayloads_.enqueue(payload);
    flushQueue();
}
