#include "InferenceManager.h"

InferenceManager::InferenceManager(QObject* parent) : QObject(parent) {}
InferenceManager::~InferenceManager() { stop(); }
void InferenceManager::configure(const MultiCameraSystemConfig& systemConfig, const InferenceRuntimeConfig& runtimeConfig) { systemConfig_ = systemConfig; runtimeConfig_ = runtimeConfig; }
bool InferenceManager::isRunning() const { return running_; }
QString InferenceManager::resolvePath(const QString& path) const { return path; }
void InferenceManager::start() { running_ = true; emit log("WCS OpenVINO C++ scheduler started."); }
void InferenceManager::stop() { running_ = false; emit allFinished(); }
void InferenceManager::startCamera(const CameraConfig&) {}
void InferenceManager::tearDownState(const QString&, PipelineState) {}
