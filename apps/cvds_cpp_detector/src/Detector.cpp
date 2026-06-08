#include "Detector.h"

#include <opencv2/dnn.hpp>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <sstream>
#include <stdexcept>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace {

#ifdef _WIN32
bool canLoadDll(const wchar_t* name) {
    HMODULE module = LoadLibraryW(name);
    if (module != nullptr) {
        FreeLibrary(module);
        return true;
    }
    return false;
}

bool canFindDll(const wchar_t* name) {
    wchar_t buffer[MAX_PATH] = {};
    return SearchPathW(nullptr, name, nullptr, MAX_PATH, buffer, nullptr) > 0;
}
#endif

}  // namespace

Detector::Detector()
    : env_(ORT_LOGGING_LEVEL_WARNING, "CVDS_Cpp_Detector") {
    sessionOptions_.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_EXTENDED);
    sessionOptions_.SetIntraOpNumThreads(1);
}

void Detector::load(
    const std::wstring& modelPath,
    int inputSize,
    float confidenceThreshold,
    float iouThreshold,
    std::vector<std::string> labels,
    DeviceMode deviceMode,
    int classFilterId
) {
    if (modelPath.empty()) {
        throw std::runtime_error("ONNX 模型路径为空");
    }
    inputSize_ = std::max(160, inputSize);
    confidenceThreshold_ = std::clamp(confidenceThreshold, 0.01f, 0.99f);
    iouThreshold_ = std::clamp(iouThreshold, 0.01f, 0.99f);
    classFilterId_ = classFilterId;
    labels_ = std::move(labels);

    if (deviceMode == DeviceMode::Gpu) {
        const std::string gpuDiagnostic = diagnoseGpuEnvironment();
        if (gpuDiagnostic.find("缺少") != std::string::npos) {
            throw std::runtime_error("GPU 推理环境不完整。\n" + gpuDiagnostic);
        }
        try {
            Ort::CUDAProviderOptions cudaOptions;
            cudaOptions.Update({{"device_id", "0"}});
            sessionOptions_.AppendExecutionProvider_CUDA_V2(*cudaOptions);
            providerName_ = "CUDAExecutionProvider";
        } catch (const std::exception& ex) {
            throw std::runtime_error(
                std::string("GPU 推理初始化失败：") + ex.what() + "\n" + diagnoseGpuEnvironment()
            );
        }
    } else {
        providerName_ = "CPUExecutionProvider";
    }

    session_ = std::make_unique<Ort::Session>(env_, modelPath.c_str(), sessionOptions_);
    Ort::AllocatorWithDefaultOptions allocator;
    auto inputName = session_->GetInputNameAllocated(0, allocator);
    auto outputName = session_->GetOutputNameAllocated(0, allocator);
    inputName_ = inputName.get();
    outputName_ = outputName.get();
}

bool Detector::isLoaded() const {
    return session_ != nullptr;
}

const std::vector<std::string>& Detector::labels() const {
    return labels_;
}

const std::string& Detector::providerName() const {
    return providerName_;
}

std::string Detector::diagnoseGpuEnvironment() {
#ifdef _WIN32
    struct RequiredDll {
        const wchar_t* wideName;
        const char* narrowName;
        const char* label;
    };
    const std::vector<RequiredDll> providerDlls = {
        {L"onnxruntime_providers_cuda.dll", "onnxruntime_providers_cuda.dll", "ONNX Runtime CUDA Provider"},
        {L"onnxruntime_providers_shared.dll", "onnxruntime_providers_shared.dll", "ONNX Runtime Shared Provider"}
    };
    const std::vector<RequiredDll> runtimeDlls = {
        {L"cudart64_12.dll", "cudart64_12.dll", "CUDA Runtime 12"},
        {L"cublas64_12.dll", "cublas64_12.dll", "cuBLAS 12"},
        {L"cublasLt64_12.dll", "cublasLt64_12.dll", "cuBLASLt 12"},
        {L"cufft64_11.dll", "cufft64_11.dll", "cuFFT 11"},
        {L"cudnn64_9.dll", "cudnn64_9.dll", "cuDNN 9"}
    };
    std::vector<std::string> missing;
    for (const RequiredDll& dll : providerDlls) {
        if (!canFindDll(dll.wideName)) {
            std::string item = dll.label;
            item += " (";
            item += dll.narrowName;
            item += ")";
            missing.push_back(item);
        }
    }
    for (const RequiredDll& dll : runtimeDlls) {
        if (!canLoadDll(dll.wideName)) {
            std::string item = dll.label;
            item += " (";
            item += dll.narrowName;
            item += ")";
            missing.push_back(item);
        }
    }

    std::ostringstream stream;
    if (missing.empty()) {
        stream << "GPU 依赖检查通过：ONNX Runtime CUDA Provider、CUDA Runtime、cuBLAS、cuFFT、cuDNN 可加载。";
    } else {
        stream << "缺少 GPU 依赖：";
        for (size_t i = 0; i < missing.size(); ++i) {
            if (i > 0) {
                stream << "；";
            }
            stream << missing[i];
        }
        stream << "。请安装 CUDA 12 运行库和 cuDNN 9，或把对应 DLL 放到 exe 同目录/PATH。";
    }
    return stream.str();
#else
    return "GPU 依赖检查当前只在 Windows 版本实现。";
#endif
}

Detector::LetterboxResult Detector::letterbox(const cv::Mat& bgrImage) const {
    if (bgrImage.empty()) {
        throw std::runtime_error("输入图像为空");
    }
    const int srcW = bgrImage.cols;
    const int srcH = bgrImage.rows;
    const float scale = std::min(static_cast<float>(inputSize_) / srcW, static_cast<float>(inputSize_) / srcH);
    const int resizedW = static_cast<int>(std::round(srcW * scale));
    const int resizedH = static_cast<int>(std::round(srcH * scale));
    const int padX = (inputSize_ - resizedW) / 2;
    const int padY = (inputSize_ - resizedH) / 2;

    cv::Mat resized;
    cv::resize(bgrImage, resized, cv::Size(resizedW, resizedH));

    cv::Mat canvas(inputSize_, inputSize_, CV_8UC3, cv::Scalar(114, 114, 114));
    resized.copyTo(canvas(cv::Rect(padX, padY, resizedW, resizedH)));

    cv::Mat rgb;
    cv::cvtColor(canvas, rgb, cv::COLOR_BGR2RGB);

    cv::Mat blob = cv::dnn::blobFromImage(
        rgb,
        1.0 / 255.0,
        cv::Size(inputSize_, inputSize_),
        cv::Scalar(),
        false,
        false,
        CV_32F
    );

    return {blob, scale, static_cast<float>(padX), static_cast<float>(padY)};
}

std::vector<Detection> Detector::infer(const cv::Mat& bgrImage) {
    if (!session_) {
        throw std::runtime_error("ONNX 模型尚未加载");
    }

    LetterboxResult prep = letterbox(bgrImage);
    std::array<int64_t, 4> inputShape = {1, 3, inputSize_, inputSize_};
    const size_t tensorSize = static_cast<size_t>(prep.blob.total());

    Ort::MemoryInfo memoryInfo = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    Ort::Value inputTensor = Ort::Value::CreateTensor<float>(
        memoryInfo,
        reinterpret_cast<float*>(prep.blob.data),
        tensorSize,
        inputShape.data(),
        inputShape.size()
    );

    const char* inputNames[] = {inputName_.c_str()};
    const char* outputNames[] = {outputName_.c_str()};
    auto outputs = session_->Run(
        Ort::RunOptions{nullptr},
        inputNames,
        &inputTensor,
        1,
        outputNames,
        1
    );

    const float* outputData = outputs.front().GetTensorData<float>();
    auto outputInfo = outputs.front().GetTensorTypeAndShapeInfo();
    std::vector<int64_t> outputShape = outputInfo.GetShape();
    return decodeOutput(outputData, outputShape, bgrImage.size(), prep);
}

std::vector<Detection> Detector::decodeOutput(
    const float* data,
    const std::vector<int64_t>& shape,
    const cv::Size& originalSize,
    const LetterboxResult& letterboxResult
) const {
    if (shape.size() != 3) {
        throw std::runtime_error("当前只支持 YOLO 常见三维输出：[1, boxes, channels] 或 [1, channels, boxes]");
    }

    int64_t dimA = shape[1];
    int64_t dimB = shape[2];
    const bool channelFirst = dimA < dimB;
    const int64_t channels = channelFirst ? dimA : dimB;
    const int64_t boxesCount = channelFirst ? dimB : dimA;
    if (channels < 5 || boxesCount <= 0) {
        throw std::runtime_error("ONNX 输出维度不符合 YOLO 检测头格式");
    }
    if (!channelFirst && channels == 6 && boxesCount <= 1000) {
        return decodeEndToEndOutput(data, boxesCount, originalSize, letterboxResult);
    }

    std::vector<cv::Rect> boxes;
    std::vector<float> scores;
    std::vector<int> classIds;

    auto valueAt = [&](int64_t boxIndex, int64_t channelIndex) -> float {
        if (channelFirst) {
            return data[channelIndex * boxesCount + boxIndex];
        }
        return data[boxIndex * channels + channelIndex];
    };

    for (int64_t i = 0; i < boxesCount; ++i) {
        const float cx = valueAt(i, 0);
        const float cy = valueAt(i, 1);
        const float w = valueAt(i, 2);
        const float h = valueAt(i, 3);

        int classId = 0;
        float confidence = valueAt(i, 4);
        if (channels > 5) {
            confidence = 0.0f;
            for (int64_t c = 4; c < channels; ++c) {
                const float score = valueAt(i, c);
                if (score > confidence) {
                    confidence = score;
                    classId = static_cast<int>(c - 4);
                }
            }
        }
        if (confidence < confidenceThreshold_) {
            continue;
        }
        if (classFilterId_ >= 0 && classId != classFilterId_) {
            continue;
        }

        float x1 = cx - w * 0.5f;
        float y1 = cy - h * 0.5f;
        float x2 = cx + w * 0.5f;
        float y2 = cy + h * 0.5f;

        x1 = (x1 - letterboxResult.padX) / letterboxResult.scale;
        y1 = (y1 - letterboxResult.padY) / letterboxResult.scale;
        x2 = (x2 - letterboxResult.padX) / letterboxResult.scale;
        y2 = (y2 - letterboxResult.padY) / letterboxResult.scale;

        x1 = std::clamp(x1, 0.0f, static_cast<float>(originalSize.width - 1));
        y1 = std::clamp(y1, 0.0f, static_cast<float>(originalSize.height - 1));
        x2 = std::clamp(x2, 0.0f, static_cast<float>(originalSize.width - 1));
        y2 = std::clamp(y2, 0.0f, static_cast<float>(originalSize.height - 1));
        if (x2 <= x1 || y2 <= y1) {
            continue;
        }

        boxes.emplace_back(
            cv::Point(static_cast<int>(std::round(x1)), static_cast<int>(std::round(y1))),
            cv::Point(static_cast<int>(std::round(x2)), static_cast<int>(std::round(y2)))
        );
        scores.push_back(confidence);
        classIds.push_back(classId);
    }

    std::vector<int> kept;
    cv::dnn::NMSBoxes(boxes, scores, confidenceThreshold_, iouThreshold_, kept);

    std::vector<Detection> detections;
    detections.reserve(kept.size());
    for (int index : kept) {
        detections.push_back({classIds[index], scores[index], boxes[index]});
    }
    return detections;
}

std::vector<Detection> Detector::decodeEndToEndOutput(
    const float* data,
    int64_t boxesCount,
    const cv::Size& originalSize,
    const LetterboxResult& letterboxResult
) const {
    std::vector<Detection> detections;
    detections.reserve(static_cast<size_t>(boxesCount));

    for (int64_t i = 0; i < boxesCount; ++i) {
        const float* row = data + i * 6;
        float x1 = row[0];
        float y1 = row[1];
        float x2 = row[2];
        float y2 = row[3];
        const float confidence = row[4];
        const int classId = static_cast<int>(std::round(row[5]));
        if (confidence < confidenceThreshold_) {
            continue;
        }
        if (classFilterId_ >= 0 && classId != classFilterId_) {
            continue;
        }

        x1 = (x1 - letterboxResult.padX) / letterboxResult.scale;
        y1 = (y1 - letterboxResult.padY) / letterboxResult.scale;
        x2 = (x2 - letterboxResult.padX) / letterboxResult.scale;
        y2 = (y2 - letterboxResult.padY) / letterboxResult.scale;

        x1 = std::clamp(x1, 0.0f, static_cast<float>(originalSize.width - 1));
        y1 = std::clamp(y1, 0.0f, static_cast<float>(originalSize.height - 1));
        x2 = std::clamp(x2, 0.0f, static_cast<float>(originalSize.width - 1));
        y2 = std::clamp(y2, 0.0f, static_cast<float>(originalSize.height - 1));
        if (x2 <= x1 || y2 <= y1) {
            continue;
        }

        detections.push_back({
            classId,
            confidence,
            cv::Rect(
                cv::Point(static_cast<int>(std::round(x1)), static_cast<int>(std::round(y1))),
                cv::Point(static_cast<int>(std::round(x2)), static_cast<int>(std::round(y2)))
            )
        });
    }
    return detections;
}

cv::Mat Detector::drawDetections(const cv::Mat& bgrImage, const std::vector<Detection>& detections) const {
    cv::Mat output = bgrImage.clone();
    for (const Detection& det : detections) {
        cv::rectangle(output, det.box, cv::Scalar(0, 229, 255), 2);
        const std::string name = (det.classId >= 0 && det.classId < static_cast<int>(labels_.size()))
            ? labels_[det.classId]
            : std::to_string(det.classId);
        const std::string text = name + " " + cv::format("%.2f", det.confidence);
        int baseline = 0;
        cv::Size textSize = cv::getTextSize(text, cv::FONT_HERSHEY_SIMPLEX, 0.55, 1, &baseline);
        cv::Rect labelRect(
            det.box.x,
            std::max(0, det.box.y - textSize.height - 8),
            textSize.width + 8,
            textSize.height + 8
        );
        cv::rectangle(output, labelRect, cv::Scalar(22, 28, 38), cv::FILLED);
        cv::putText(
            output,
            text,
            cv::Point(labelRect.x + 4, labelRect.y + labelRect.height - 4),
            cv::FONT_HERSHEY_SIMPLEX,
            0.55,
            cv::Scalar(0, 229, 255),
            1
        );
    }
    return output;
}
