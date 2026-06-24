#include "inference/DetectorBackend.h"

InferenceBackend inferenceBackendFromString(const QString& value) {
    const QString normalized = value.trimmed().toLower();
    if (normalized == "tensorrt" || normalized == "trt") {
        return InferenceBackend::TensorRt;
    }
    return InferenceBackend::OpenVino;
}

QString inferenceBackendName(InferenceBackend backend) {
    return backend == InferenceBackend::TensorRt ? "TensorRT" : "OpenVINO";
}

bool DetectorBackend::load(
    InferenceBackend backend,
    const QString& modelPath,
    const QString& device,
    int inputSize,
    QString* error) {
    backend_ = backend;
    if (backend_ == InferenceBackend::TensorRt) {
        Q_UNUSED(device);
        return tensorRt_.load(modelPath, inputSize, error);
    }
    return openVino_.load(modelPath, device, inputSize, error);
}

DetectionResults DetectorBackend::infer(
    const cv::Mat& frame,
    float confidence,
    float iou,
    int classFilterId,
    QString* error) {
    if (backend_ == InferenceBackend::TensorRt) {
        return tensorRt_.infer(frame, confidence, iou, classFilterId, error);
    }
    return openVino_.infer(frame, confidence, iou, classFilterId, error);
}

bool DetectorBackend::isLoaded() const {
    return backend_ == InferenceBackend::TensorRt ? tensorRt_.isLoaded() : openVino_.isLoaded();
}
