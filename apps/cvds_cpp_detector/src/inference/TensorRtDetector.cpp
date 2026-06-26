#include "inference/TensorRtDetector.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <stdexcept>

#ifdef CVDS_WITH_TENSORRT
#include <NvInfer.h>
#include <cuda_runtime_api.h>
#include <cuda_fp16.h>
#endif

namespace {

#ifdef CVDS_WITH_TENSORRT
class TensorRtLogger final : public nvinfer1::ILogger {
public:
    void log(Severity severity, const char* message) noexcept override {
        if (severity <= Severity::kWARNING && message != nullptr) {
            lastMessage_ = message;
        }
    }
    std::string lastMessage_;
};

template <typename T>
void destroyTensorRt(T* ptr) {
    delete ptr;
}

size_t volume(const nvinfer1::Dims& dims) {
    size_t total = 1;
    for (int i = 0; i < dims.nbDims; ++i) {
        if (dims.d[i] <= 0) return 0;
        total *= static_cast<size_t>(dims.d[i]);
    }
    return total;
}

std::vector<size_t> toShape(const nvinfer1::Dims& dims) {
    std::vector<size_t> shape;
    shape.reserve(static_cast<size_t>(std::max(0, dims.nbDims)));
    for (int i = 0; i < dims.nbDims; ++i) {
        if (dims.d[i] > 0) shape.push_back(static_cast<size_t>(dims.d[i]));
    }
    return shape;
}

size_t dataTypeBytes(nvinfer1::DataType type) {
    switch (type) {
    case nvinfer1::DataType::kFLOAT:
        return sizeof(float);
    case nvinfer1::DataType::kHALF:
        return sizeof(__half);
    case nvinfer1::DataType::kINT32:
        return sizeof(int32_t);
    case nvinfer1::DataType::kINT64:
        return sizeof(int64_t);
    case nvinfer1::DataType::kINT8:
    case nvinfer1::DataType::kUINT8:
    case nvinfer1::DataType::kBOOL:
        return 1;
    default:
        return 0;
    }
}

QString cudaErrorText(cudaError_t code, const QString& action) {
    return action + " 失败：" + QString::fromUtf8(cudaGetErrorString(code));
}
#endif

YoloOutputLayout readOutputLayoutFromMetadata(const QFileInfo& engineInfo) {
    QStringList candidates;
    candidates << engineInfo.dir().filePath("metadata.yaml")
               << engineInfo.dir().filePath(engineInfo.completeBaseName() + ".yaml");
    for (const QString& path : candidates) {
        QFile metadata(path);
        if (!metadata.open(QIODevice::ReadOnly | QIODevice::Text)) continue;
        bool endToEnd = false;
        QString task;
        while (!metadata.atEnd()) {
            const QString line = QString::fromUtf8(metadata.readLine()).trimmed();
            if (line.startsWith("end2end:", Qt::CaseInsensitive)) {
                const QString value = line.section(':', 1).trimmed().toLower();
                endToEnd = (value == "true" || value == "1" || value == "yes");
            } else if (line.startsWith("task:", Qt::CaseInsensitive)) {
                task = line.section(':', 1).trimmed().toLower();
            }
        }
        if (endToEnd && (task == "segment" || task == "detect")) {
            return YoloOutputLayout::EndToEnd;
        }
    }
    return YoloOutputLayout::Auto;
}

}  // namespace

struct TensorRtDetector::Impl {
#ifdef CVDS_WITH_TENSORRT
    struct OutputBinding {
        std::string name;
        nvinfer1::Dims dims{};
        nvinfer1::DataType type = nvinfer1::DataType::kFLOAT;
        void* device = nullptr;
        std::vector<uint8_t> host;
        size_t bytes = 0;
    };

    TensorRtLogger logger;
    std::unique_ptr<nvinfer1::IRuntime, void (*)(nvinfer1::IRuntime*)> runtime{nullptr, destroyTensorRt};
    std::unique_ptr<nvinfer1::ICudaEngine, void (*)(nvinfer1::ICudaEngine*)> engine{nullptr, destroyTensorRt};
    std::unique_ptr<nvinfer1::IExecutionContext, void (*)(nvinfer1::IExecutionContext*)> context{nullptr, destroyTensorRt};
    cudaStream_t stream = nullptr;
    void* inputDevice = nullptr;
    std::vector<OutputBinding> outputBindings;
    std::string inputName;
    nvinfer1::Dims inputDims{};
    size_t inputBytes = 0;

    ~Impl() {
        if (inputDevice != nullptr) cudaFree(inputDevice);
        for (OutputBinding& output : outputBindings) {
            if (output.device != nullptr) cudaFree(output.device);
        }
        if (stream != nullptr) cudaStreamDestroy(stream);
    }

    DetectionResults parseOutputBinding(
        const OutputBinding& output,
        const LetterBoxInfo& meta,
        const YoloPostprocessConfig& config) const {
        const std::vector<size_t> dims = toShape(output.dims);
        const size_t total = volume(output.dims);
        if (total == 0) return {};
        if (output.type == nvinfer1::DataType::kFLOAT) {
            return parseYoloTensor(reinterpret_cast<const float*>(output.host.data()), dims, meta, config);
        }
        std::vector<float> buffer(total, 0.0f);
        if (output.type == nvinfer1::DataType::kHALF) {
            const auto* src = reinterpret_cast<const __half*>(output.host.data());
            for (size_t i = 0; i < total; ++i) buffer[i] = __half2float(src[i]);
        } else if (output.type == nvinfer1::DataType::kINT32) {
            const auto* src = reinterpret_cast<const int32_t*>(output.host.data());
            for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
        } else if (output.type == nvinfer1::DataType::kINT64) {
            const auto* src = reinterpret_cast<const int64_t*>(output.host.data());
            for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
        } else if (output.type == nvinfer1::DataType::kINT8) {
            const auto* src = reinterpret_cast<const int8_t*>(output.host.data());
            for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
        } else if (output.type == nvinfer1::DataType::kUINT8 || output.type == nvinfer1::DataType::kBOOL) {
            const auto* src = reinterpret_cast<const uint8_t*>(output.host.data());
            for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
        } else {
            return {};
        }
        return parseYoloTensor(buffer.data(), dims, meta, config);
    }
#endif
};

TensorRtDetector::TensorRtDetector() : impl_(std::make_unique<Impl>()) {}

TensorRtDetector::~TensorRtDetector() = default;

void TensorRtDetector::reset() {
    impl_ = std::make_unique<Impl>();
    modelPath_.clear();
    outputLayout_ = YoloOutputLayout::Auto;
    loaded_ = false;
}

bool TensorRtDetector::load(const QString& modelPath, const QString& device, int inputSize, QString* error) {
    reset();
    if (error) error->clear();

#ifndef CVDS_WITH_TENSORRT
    Q_UNUSED(modelPath);
    Q_UNUSED(device);
    Q_UNUSED(inputSize);
    if (error) *error = "当前程序未启用 TensorRT，请使用带 TensorRT SDK 构建的版本。";
    return false;
#else
    try {
        bool parsedDevice = false;
        const QString trimmedDevice = device.trimmed();
        const int cudaDevice = trimmedDevice.isEmpty() ? 0 : trimmedDevice.toInt(&parsedDevice);
        if (!trimmedDevice.isEmpty() && !parsedDevice) {
            if (error) *error = "TensorRT 执行设备必须是 NVIDIA CUDA GPU 编号，例如 0。";
            return false;
        }
        cudaError_t cudaStatus = cudaSetDevice(cudaDevice);
        if (cudaStatus != cudaSuccess) {
            if (error) *error = cudaErrorText(cudaStatus, "选择 NVIDIA CUDA GPU " + QString::number(cudaDevice));
            return false;
        }

        const QString enginePath = modelPath.trimmed();
        const QFileInfo info(enginePath);
        if (!info.isFile() || !(enginePath.endsWith(".engine", Qt::CaseInsensitive)
                                || enginePath.endsWith(".plan", Qt::CaseInsensitive))) {
            if (error) *error = "TensorRT 只支持已构建的 .engine 或 .plan 文件。";
            return false;
        }

        QFile file(enginePath);
        if (!file.open(QIODevice::ReadOnly)) {
            if (error) *error = "无法读取 TensorRT engine：" + enginePath;
            return false;
        }
        const QByteArray engineData = file.readAll();
        if (engineData.isEmpty()) {
            if (error) *error = "TensorRT engine 文件为空：" + enginePath;
            return false;
        }

        impl_->runtime.reset(nvinfer1::createInferRuntime(impl_->logger));
        if (!impl_->runtime) throw std::runtime_error("createInferRuntime 返回空指针");
        impl_->engine.reset(impl_->runtime->deserializeCudaEngine(engineData.constData(), static_cast<size_t>(engineData.size())));
        if (!impl_->engine) throw std::runtime_error("deserializeCudaEngine 返回空指针");
        impl_->context.reset(impl_->engine->createExecutionContext());
        if (!impl_->context) throw std::runtime_error("createExecutionContext 返回空指针");

        std::vector<std::string> inputs;
        std::vector<std::string> outputs;
        const int nbTensors = impl_->engine->getNbIOTensors();
        for (int i = 0; i < nbTensors; ++i) {
            const char* name = impl_->engine->getIOTensorName(i);
            if (name == nullptr) continue;
            if (impl_->engine->getTensorIOMode(name) == nvinfer1::TensorIOMode::kINPUT) {
                inputs.emplace_back(name);
            } else {
                outputs.emplace_back(name);
            }
        }
        if (inputs.size() != 1 || outputs.empty()) {
            if (error) *error = "TensorRT engine 必须有 1 个输入和至少 1 个输出。";
            return false;
        }

        inputWidth_ = std::max(32, inputSize);
        inputHeight_ = inputWidth_;
        impl_->inputName = inputs.front();
        impl_->inputDims = impl_->engine->getTensorShape(impl_->inputName.c_str());
        if (impl_->inputDims.nbDims != 4) {
            if (error) *error = "TensorRT 输入必须是 NCHW 四维张量。";
            return false;
        }
        impl_->inputDims.d[0] = 1;
        impl_->inputDims.d[1] = 3;
        impl_->inputDims.d[2] = inputHeight_;
        impl_->inputDims.d[3] = inputWidth_;
        if (!impl_->context->setInputShape(impl_->inputName.c_str(), impl_->inputDims)) {
            if (error) *error = "TensorRT 设置输入尺寸失败。";
            return false;
        }

        const size_t inputCount = volume(impl_->inputDims);
        if (inputCount == 0) {
            if (error) *error = "TensorRT engine 输入尺寸无效。";
            return false;
        }
        impl_->inputBytes = inputCount * sizeof(float);
        impl_->outputBindings.clear();
        impl_->outputBindings.reserve(outputs.size());
        for (const std::string& outputName : outputs) {
            TensorRtDetector::Impl::OutputBinding binding;
            binding.name = outputName;
            binding.dims = impl_->context->getTensorShape(outputName.c_str());
            const size_t outputCount = volume(binding.dims);
            binding.type = impl_->engine->getTensorDataType(outputName.c_str());
            const size_t elementBytes = dataTypeBytes(binding.type);
            if (outputCount == 0 || elementBytes == 0) {
                if (error) *error = "TensorRT engine 输出尺寸或类型无效：" + QString::fromStdString(outputName);
                return false;
            }
            binding.bytes = outputCount * elementBytes;
            binding.host.assign(binding.bytes, 0);
            impl_->outputBindings.push_back(std::move(binding));
        }

        cudaStatus = cudaStreamCreate(&impl_->stream);
        if (cudaStatus != cudaSuccess) {
            if (error) *error = cudaErrorText(cudaStatus, "创建 CUDA stream");
            return false;
        }
        cudaStatus = cudaMalloc(&impl_->inputDevice, impl_->inputBytes);
        if (cudaStatus != cudaSuccess) {
            if (error) *error = cudaErrorText(cudaStatus, "分配 TensorRT 输入显存");
            return false;
        }
        for (TensorRtDetector::Impl::OutputBinding& output : impl_->outputBindings) {
            cudaStatus = cudaMalloc(&output.device, output.bytes);
            if (cudaStatus != cudaSuccess) {
                if (error) *error = cudaErrorText(cudaStatus, "分配 TensorRT 输出显存");
                return false;
            }
        }
        if (!impl_->context->setTensorAddress(impl_->inputName.c_str(), impl_->inputDevice)) {
            if (error) *error = "TensorRT 绑定输入显存失败。";
            return false;
        }
        for (TensorRtDetector::Impl::OutputBinding& output : impl_->outputBindings) {
            if (!impl_->context->setTensorAddress(output.name.c_str(), output.device)) {
                if (error) *error = "TensorRT 绑定输出显存失败：" + QString::fromStdString(output.name);
                return false;
            }
        }

        modelPath_ = enginePath;
        outputLayout_ = readOutputLayoutFromMetadata(info);
        loaded_ = true;
        return true;
    } catch (const std::exception& ex) {
        if (error) *error = QString::fromUtf8(ex.what());
        return false;
    }
#endif
}

DetectionResults TensorRtDetector::infer(
    const cv::Mat& frame,
    float confidence,
    float iou,
    int classFilterId,
    QString* error) {
    if (error) error->clear();
    if (!loaded_) {
        if (error) *error = "TensorRT detector is not loaded";
        return {};
    }
    if (frame.empty()) {
        if (error) *error = "输入画面为空";
        return {};
    }
    if (frame.type() != CV_8UC3) {
        if (error) *error = "输入画面必须是 CV_8UC3 BGR";
        return {};
    }

#ifndef CVDS_WITH_TENSORRT
    Q_UNUSED(frame);
    Q_UNUSED(confidence);
    Q_UNUSED(iou);
    Q_UNUSED(classFilterId);
    if (error) *error = "当前程序未启用 TensorRT。";
    return {};
#else
    try {
        LetterBoxInfo meta;
        const cv::Mat padded = letterboxImage(frame, inputWidth_, inputHeight_, &meta);
        if (padded.empty()) throw std::runtime_error("letterbox 预处理失败");
        cv::Mat rgb;
        cv::cvtColor(padded, rgb, cv::COLOR_BGR2RGB);
        cv::Mat f32;
        rgb.convertTo(f32, CV_32F, 1.0 / 255.0);
        std::vector<cv::Mat> channels;
        cv::split(f32, channels);
        if (channels.size() != 3) {
            if (error) *error = "预处理失败：RGB 通道数异常";
            return {};
        }
        std::vector<float> inputHost(static_cast<size_t>(inputWidth_) * static_cast<size_t>(inputHeight_) * 3U);
        const size_t planeSize = static_cast<size_t>(inputWidth_) * static_cast<size_t>(inputHeight_);
        for (size_t c = 0; c < 3; ++c) {
            const cv::Mat continuous = channels[c].isContinuous() ? channels[c] : channels[c].clone();
            std::memcpy(inputHost.data() + c * planeSize, continuous.ptr<float>(), planeSize * sizeof(float));
        }

        cudaError_t cudaStatus = cudaMemcpyAsync(
            impl_->inputDevice,
            inputHost.data(),
            impl_->inputBytes,
            cudaMemcpyHostToDevice,
            impl_->stream);
        if (cudaStatus != cudaSuccess) {
            if (error) *error = cudaErrorText(cudaStatus, "复制 TensorRT 输入");
            return {};
        }
        if (!impl_->context->enqueueV3(impl_->stream)) {
            if (error) *error = "TensorRT enqueueV3 推理失败。";
            return {};
        }
        for (TensorRtDetector::Impl::OutputBinding& output : impl_->outputBindings) {
            cudaStatus = cudaMemcpyAsync(
                output.host.data(),
                output.device,
                output.bytes,
                cudaMemcpyDeviceToHost,
                impl_->stream);
            if (cudaStatus != cudaSuccess) {
                if (error) *error = cudaErrorText(cudaStatus, "复制 TensorRT 输出");
                return {};
            }
        }
        cudaStatus = cudaStreamSynchronize(impl_->stream);
        if (cudaStatus != cudaSuccess) {
            if (error) *error = cudaErrorText(cudaStatus, "同步 TensorRT 输出");
            return {};
        }

        YoloPostprocessConfig config;
        config.confidence = confidence;
        config.iou = iou;
        config.classFilterId = classFilterId;
        config.outputLayout = outputLayout_;
        DetectionResults best;
        for (const TensorRtDetector::Impl::OutputBinding& output : impl_->outputBindings) {
            DetectionResults parsed = impl_->parseOutputBinding(output, meta, config);
            if (parsed.empty()) continue;
            if (best.empty() || parsed.size() > best.size()) {
                best = std::move(parsed);
            }
        }
        return best;
    } catch (const std::exception& ex) {
        if (error) *error = QString::fromUtf8(ex.what());
        return {};
    }
#endif
}

DetectionResults TensorRtDetector::parseOutput(
    const float* output,
    const std::vector<size_t>& dims,
    const LetterBoxInfo& meta,
    const YoloPostprocessConfig& config) const {
    return parseYoloTensor(output, dims, meta, config);
}
