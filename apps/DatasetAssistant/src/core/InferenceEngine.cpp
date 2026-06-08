#include "core/InferenceEngine.h"

#include <opencv2/imgproc.hpp>

#if DATASET_ASSISTANT_HAS_ONNXRUNTIME
#include <onnxruntime_cxx_api.h>
#endif

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>

namespace {

#if DATASET_ASSISTANT_HAS_ONNXRUNTIME
struct OrtSessionDeleter {
    void operator()(Ort::Session* session) const {
        delete session;
    }
};
#endif

double areaOf(const BBox& box) {
    return std::max(0.0, box.x2 - box.x1) * std::max(0.0, box.y2 - box.y1);
}

double iouOf(const BBox& a, const BBox& b) {
    const double x1 = std::max(a.x1, b.x1);
    const double y1 = std::max(a.y1, b.y1);
    const double x2 = std::min(a.x2, b.x2);
    const double y2 = std::min(a.y2, b.y2);
    const double intersection = std::max(0.0, x2 - x1) * std::max(0.0, y2 - y1);
    const double unionArea = areaOf(a) + areaOf(b) - intersection;
    return unionArea <= 0.0 ? 0.0 : intersection / unionArea;
}

double clampDouble(double value, double low, double high) {
    return std::max(low, std::min(value, high));
}

float valueAt(const std::vector<float>& output, YoloOutputShape shape, int boxIndex, int featureIndex, bool transposed) {
    if (transposed) {
        return output[static_cast<size_t>(featureIndex * shape.cols + boxIndex)];
    }
    return output[static_cast<size_t>(boxIndex * shape.cols + featureIndex)];
}

std::vector<DetectionResult> parseYoloCandidates(const std::vector<float>& output,
                                                 YoloOutputShape shape,
                                                 int imageWidth,
                                                 int imageHeight,
                                                 const InferenceConfig& config,
                                                 bool transposed) {
    const int boxCount = transposed ? shape.cols : shape.rows;
    const int featureCount = transposed ? shape.rows : shape.cols;
    if (boxCount <= 0 || featureCount < 6 || imageWidth <= 0 || imageHeight <= 0) {
        return {};
    }

    const bool hasExplicitObjectness = !config.classNames.empty() && featureCount == static_cast<int>(config.classNames.size()) + 5;
    const int classStart = hasExplicitObjectness ? 5 : 4;
    if (classStart >= featureCount) {
        return {};
    }

    const double scale = std::min(static_cast<double>(config.inputWidth) / imageWidth,
                                  static_cast<double>(config.inputHeight) / imageHeight);
    if (scale <= 0.0 || !std::isfinite(scale)) {
        return {};
    }
    const double paddedWidth = imageWidth * scale;
    const double paddedHeight = imageHeight * scale;
    const double padX = (config.inputWidth - paddedWidth) / 2.0;
    const double padY = (config.inputHeight - paddedHeight) / 2.0;

    std::vector<DetectionResult> detections;
    for (int boxIndex = 0; boxIndex < boxCount; ++boxIndex) {
        int bestClass = -1;
        float bestClassScore = -std::numeric_limits<float>::infinity();
        for (int featureIndex = classStart; featureIndex < featureCount; ++featureIndex) {
            const float score = valueAt(output, shape, boxIndex, featureIndex, transposed);
            if (score > bestClassScore) {
                bestClassScore = score;
                bestClass = featureIndex - classStart;
            }
        }

        const float objectness = hasExplicitObjectness ? valueAt(output, shape, boxIndex, 4, transposed) : 1.0f;
        const double confidence = static_cast<double>(objectness * bestClassScore);
        if (bestClass < 0 || confidence < config.confidenceThreshold) {
            continue;
        }

        const double cx = valueAt(output, shape, boxIndex, 0, transposed);
        const double cy = valueAt(output, shape, boxIndex, 1, transposed);
        const double width = valueAt(output, shape, boxIndex, 2, transposed);
        const double height = valueAt(output, shape, boxIndex, 3, transposed);
        if (width <= 0.0 || height <= 0.0) {
            continue;
        }

        BBox box;
        box.x1 = ((cx - width / 2.0) - padX) / scale;
        box.y1 = ((cy - height / 2.0) - padY) / scale;
        box.x2 = ((cx + width / 2.0) - padX) / scale;
        box.y2 = ((cy + height / 2.0) - padY) / scale;
        box.x1 = clampDouble(box.x1, 0.0, imageWidth);
        box.y1 = clampDouble(box.y1, 0.0, imageHeight);
        box.x2 = clampDouble(box.x2, 0.0, imageWidth);
        box.y2 = clampDouble(box.y2, 0.0, imageHeight);
        if (areaOf(box) <= 0.0) {
            continue;
        }

        DetectionResult detection;
        detection.classId = bestClass;
        if (bestClass >= 0 && bestClass < static_cast<int>(config.classNames.size())) {
            detection.className = config.classNames[static_cast<size_t>(bestClass)];
        }
        detection.box = box;
        detection.confidence = confidence;
        detections.push_back(detection);
    }

    std::sort(detections.begin(), detections.end(), [](const DetectionResult& a, const DetectionResult& b) {
        return a.confidence > b.confidence;
    });

    std::vector<DetectionResult> kept;
    for (const DetectionResult& candidate : detections) {
        bool suppressed = false;
        for (const DetectionResult& existing : kept) {
            if (candidate.classId == existing.classId && iouOf(candidate.box, existing.box) > config.iouThreshold) {
                suppressed = true;
                break;
            }
        }
        if (!suppressed) {
            kept.push_back(candidate);
        }
    }
    return kept;
}

} // namespace

struct InferenceEngine::Impl {
#if DATASET_ASSISTANT_HAS_ONNXRUNTIME
    Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "DatasetAssistant"};
    Ort::SessionOptions sessionOptions;
    std::unique_ptr<Ort::Session, OrtSessionDeleter> session;
    std::vector<std::string> inputNames;
    std::vector<std::string> outputNames;
#endif
};

InferenceEngine::InferenceEngine()
    : impl_(std::make_unique<Impl>()) {
}

InferenceEngine::~InferenceEngine() = default;

bool InferenceEngine::loadModel(const std::filesystem::path& modelPath, const InferenceConfig& config) {
    config_ = config;
    config_.modelPath = modelPath;
    loaded_ = false;
    providerName_ = "CPUExecutionProvider";
    if (!std::filesystem::exists(modelPath)) {
        return false;
    }

    GpuDiagnostic diag = diagnoseGpu();
    if (config.devicePolicy == DevicePolicy::Gpu && !diag.cudaProviderAvailable) {
        providerName_ = "GPU unavailable";
        return false;
    }
    providerName_ = diag.cudaProviderAvailable && config.devicePolicy != DevicePolicy::Cpu ? "CUDAExecutionProvider" : "CPUExecutionProvider";

#if DATASET_ASSISTANT_HAS_ONNXRUNTIME
    auto tryOpenSession = [&](bool useCuda) -> bool {
        impl_->session.reset();
        impl_->inputNames.clear();
        impl_->outputNames.clear();
        impl_->sessionOptions = Ort::SessionOptions();
        impl_->sessionOptions.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        if (useCuda) {
            Ort::ThrowOnError(Ort::GetApi().SessionOptionsAppendExecutionProvider_CUDA(impl_->sessionOptions, 0));
        }

#ifdef _WIN32
        impl_->session = std::unique_ptr<Ort::Session, OrtSessionDeleter>(
            new Ort::Session(impl_->env, modelPath.wstring().c_str(), impl_->sessionOptions));
#else
        impl_->session = std::unique_ptr<Ort::Session, OrtSessionDeleter>(
            new Ort::Session(impl_->env, modelPath.string().c_str(), impl_->sessionOptions));
#endif

        Ort::AllocatorWithDefaultOptions allocator;
        const size_t inputCount = impl_->session->GetInputCount();
        const size_t outputCount = impl_->session->GetOutputCount();
        for (size_t i = 0; i < inputCount; ++i) {
            auto name = impl_->session->GetInputNameAllocated(i, allocator);
            impl_->inputNames.emplace_back(name.get());
        }
        for (size_t i = 0; i < outputCount; ++i) {
            auto name = impl_->session->GetOutputNameAllocated(i, allocator);
            impl_->outputNames.emplace_back(name.get());
        }
        return !impl_->inputNames.empty() && !impl_->outputNames.empty();
    };

    try {
        loaded_ = tryOpenSession(providerName_ == "CUDAExecutionProvider");
    } catch (const std::exception&) {
        if (config.devicePolicy == DevicePolicy::Auto && providerName_ == "CUDAExecutionProvider") {
            try {
                providerName_ = "CPUExecutionProvider";
                loaded_ = tryOpenSession(false);
            } catch (const std::exception&) {
                providerName_ = "ONNX Runtime load failed";
                loaded_ = false;
            }
        } else {
            providerName_ = "ONNX Runtime load failed";
            loaded_ = false;
        }
    }
#endif
    return loaded_;
}

std::vector<DetectionResult> InferenceEngine::infer(const cv::Mat& image) {
    if (!loaded_ || image.empty()) {
        return {};
    }

#if DATASET_ASSISTANT_HAS_ONNXRUNTIME
    try {
        const int width = config_.inputWidth;
        const int height = config_.inputHeight;
        if (width <= 0 || height <= 0 || !impl_->session || impl_->inputNames.empty() || impl_->outputNames.empty()) {
            return {};
        }

        cv::Mat rgb;
        if (image.channels() == 1) {
            cv::cvtColor(image, rgb, cv::COLOR_GRAY2RGB);
        } else {
            cv::cvtColor(image, rgb, cv::COLOR_BGR2RGB);
        }

        const double scale = std::min(static_cast<double>(width) / image.cols, static_cast<double>(height) / image.rows);
        const int resizedWidth = std::max(1, static_cast<int>(std::round(image.cols * scale)));
        const int resizedHeight = std::max(1, static_cast<int>(std::round(image.rows * scale)));
        cv::Mat resized;
        cv::resize(rgb, resized, cv::Size(resizedWidth, resizedHeight), 0.0, 0.0, cv::INTER_LINEAR);
        cv::Mat inputImage(height, width, CV_8UC3, cv::Scalar(114, 114, 114));
        const int padX = (width - resizedWidth) / 2;
        const int padY = (height - resizedHeight) / 2;
        resized.copyTo(inputImage(cv::Rect(padX, padY, resizedWidth, resizedHeight)));

        std::vector<float> inputTensorValues(static_cast<size_t>(3 * width * height));
        for (int y = 0; y < height; ++y) {
            const cv::Vec3b* row = inputImage.ptr<cv::Vec3b>(y);
            for (int x = 0; x < width; ++x) {
                const size_t pixelIndex = static_cast<size_t>(y * width + x);
                inputTensorValues[pixelIndex] = row[x][0] / 255.0f;
                inputTensorValues[static_cast<size_t>(width * height) + pixelIndex] = row[x][1] / 255.0f;
                inputTensorValues[static_cast<size_t>(2 * width * height) + pixelIndex] = row[x][2] / 255.0f;
            }
        }

        std::array<int64_t, 4> inputShape{1, 3, height, width};
        Ort::MemoryInfo memoryInfo = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        Ort::Value inputTensor = Ort::Value::CreateTensor<float>(memoryInfo,
                                                                 inputTensorValues.data(),
                                                                 inputTensorValues.size(),
                                                                 inputShape.data(),
                                                                 inputShape.size());
        std::vector<const char*> inputNames;
        std::vector<const char*> outputNames;
        for (const std::string& name : impl_->inputNames) {
            inputNames.push_back(name.c_str());
        }
        for (const std::string& name : impl_->outputNames) {
            outputNames.push_back(name.c_str());
        }

        auto outputTensors = impl_->session->Run(Ort::RunOptions{nullptr},
                                                inputNames.data(),
                                                &inputTensor,
                                                1,
                                                outputNames.data(),
                                                outputNames.size());
        if (outputTensors.empty() || !outputTensors[0].IsTensor()) {
            return {};
        }

        Ort::TensorTypeAndShapeInfo shapeInfo = outputTensors[0].GetTensorTypeAndShapeInfo();
        if (shapeInfo.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) {
            return {};
        }
        const std::vector<int64_t> outputShape = shapeInfo.GetShape();
        if (outputShape.size() < 2) {
            return {};
        }
        const int rows = static_cast<int>(outputShape[outputShape.size() - 2]);
        const int cols = static_cast<int>(outputShape[outputShape.size() - 1]);
        if (rows <= 0 || cols <= 0) {
            return {};
        }

        const size_t outputCount = shapeInfo.GetElementCount();
        const float* outputData = outputTensors[0].GetTensorData<float>();
        std::vector<float> output(outputData, outputData + outputCount);
        return postprocessYoloOutput(output, YoloOutputShape{rows, cols}, image.cols, image.rows, config_);
    } catch (const std::exception&) {
        return {};
    }
#endif
    return {};
}

std::string InferenceEngine::providerName() const {
    return providerName_;
}

std::vector<DetectionResult> InferenceEngine::postprocessYoloOutput(const std::vector<float>& output,
                                                                    YoloOutputShape shape,
                                                                    int imageWidth,
                                                                    int imageHeight,
                                                                    const InferenceConfig& config) {
    if (shape.rows <= 0 || shape.cols <= 0 || output.size() != static_cast<size_t>(shape.rows * shape.cols)) {
        return {};
    }

    if (shape.rows >= 6 && (shape.cols < 6 || shape.cols > shape.rows)) {
        return parseYoloCandidates(output, shape, imageWidth, imageHeight, config, true);
    }
    if (shape.cols >= 6) {
        return parseYoloCandidates(output, shape, imageWidth, imageHeight, config, false);
    }
    return {};
}

GpuDiagnostic InferenceEngine::diagnoseGpu() const {
    GpuDiagnostic diag;
#if DATASET_ASSISTANT_HAS_ONNXRUNTIME
    try {
        std::vector<std::string> providers = Ort::GetAvailableProviders();
        for (const auto& provider : providers) {
            if (provider == "CUDAExecutionProvider") {
                diag.cudaProviderAvailable = true;
            }
            if (provider == "CPUExecutionProvider") {
                diag.cpuProviderAvailable = true;
            }
        }
    } catch (const std::exception& ex) {
        diag.errors.push_back(ex.what());
    }
#else
    diag.errors.push_back("ONNX Runtime is not configured. Inference is built in placeholder mode.");
#endif
    return diag;
}
