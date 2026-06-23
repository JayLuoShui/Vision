#include "inference/OpenVinoDetector.h"

#include <QDir>
#include <QFileInfo>
#include <QStringList>
#include <opencv2/imgproc.hpp>

#include <algorithm>
#include <cstring>
#include <numeric>
#include <vector>

bool OpenVinoDetector::load(const QString& modelPath, const QString& device, int inputSize, QString* error) {
    try {
        QString xmlPath = modelPath;
        QFileInfo info(xmlPath);
        if (info.isDir()) {
            const QStringList xmlFiles = QDir(xmlPath).entryList(QStringList() << "*.xml", QDir::Files);
            if (xmlFiles.isEmpty()) {
                if (error) *error = "OpenVINO 模型目录中没有 .xml 文件";
                return false;
            }
            xmlPath = QDir(xmlPath).filePath(xmlFiles.first());
        }
        if (!xmlPath.endsWith(".xml", Qt::CaseInsensitive)) {
            if (error) *error = "运行端只支持 OpenVINO IR .xml 或模型目录";
            return false;
        }

        auto model = core_.read_model(xmlPath.toStdString());
        inputWidth_ = std::max(32, inputSize);
        inputHeight_ = inputWidth_;
        input_ = model->input();
        model->reshape({{input_.get_any_name(), ov::PartialShape({1, 3, static_cast<size_t>(inputHeight_), static_cast<size_t>(inputWidth_)})}});

        QString ovDevice = device.trimmed().isEmpty() ? "AUTO" : device.trimmed().toUpper();
        if (ovDevice == "0") ovDevice = "GPU";
        if (ovDevice != "AUTO" && ovDevice != "CPU" && ovDevice != "GPU" && ovDevice != "NPU") {
            if (error) *error = "OpenVINO device 只支持 AUTO / CPU / GPU / NPU";
            return false;
        }

        compiledModel_ = core_.compile_model(model, ovDevice.toStdString());
        inferRequest_ = compiledModel_.create_infer_request();
        modelPath_ = xmlPath;
        device_ = ovDevice;
        loaded_ = true;
        return true;
    } catch (const std::exception& ex) {
        loaded_ = false;
        if (error) *error = QString::fromUtf8(ex.what());
        return false;
    }
}

DetectionResults OpenVinoDetector::infer(const cv::Mat& frame, float confidence, float iou, int classFilterId, QString* error) {
    if (!loaded_) {
        if (error) *error = "OpenVINO detector is not loaded";
        return {};
    }
    if (frame.empty()) return {};

    try {
        LetterBoxInfo meta;
        const cv::Mat padded = letterboxImage(frame, inputWidth_, inputHeight_, &meta);
        cv::Mat rgb;
        cv::cvtColor(padded, rgb, cv::COLOR_BGR2RGB);
        cv::Mat f32;
        rgb.convertTo(f32, CV_32F, 1.0 / 255.0);

        ov::Tensor inputTensor(ov::element::f32, ov::Shape{1, 3, static_cast<size_t>(inputHeight_), static_cast<size_t>(inputWidth_)});
        float* dst = inputTensor.data<float>();
        const size_t planeSize = static_cast<size_t>(inputWidth_) * static_cast<size_t>(inputHeight_);
        std::vector<cv::Mat> channels;
        cv::split(f32, channels);
        if (channels.size() != 3) {
            if (error) *error = "预处理失败：RGB 通道数异常";
            return {};
        }
        for (size_t c = 0; c < 3; ++c) {
            const cv::Mat continuous = channels[c].isContinuous() ? channels[c] : channels[c].clone();
            std::memcpy(dst + c * planeSize, continuous.ptr<float>(), planeSize * sizeof(float));
        }

        inferRequest_.set_input_tensor(inputTensor);
        inferRequest_.infer();

        const ov::Tensor outputTensor = inferRequest_.get_output_tensor(0);
        YoloPostprocessConfig config;
        config.confidence = confidence;
        config.iou = iou;
        config.classFilterId = classFilterId;
        return parseOutput(outputTensor, meta, config);
    } catch (const std::exception& ex) {
        if (error) *error = QString::fromUtf8(ex.what());
        return {};
    }
}

DetectionResults OpenVinoDetector::parseOutput(const ov::Tensor& output, const LetterBoxInfo& meta, const YoloPostprocessConfig& config) const {
    const ov::Shape shape = output.get_shape();
    const std::vector<size_t> dims(shape.begin(), shape.end());
    const size_t total = output.get_size();
    if (total == 0) return {};

    if (output.get_element_type() == ov::element::f32) {
        return parseYoloTensor(output.data<const float>(), dims, meta, config);
    }

    std::vector<float> buffer(total, 0.0f);
    if (output.get_element_type() == ov::element::f16) {
        const auto* src = output.data<const ov::float16>();
        for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
    } else if (output.get_element_type() == ov::element::f64) {
        const auto* src = output.data<const double>();
        for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
    } else if (output.get_element_type() == ov::element::i32) {
        const auto* src = output.data<const int32_t>();
        for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
    } else if (output.get_element_type() == ov::element::u8) {
        const auto* src = output.data<const uint8_t>();
        for (size_t i = 0; i < total; ++i) buffer[i] = static_cast<float>(src[i]);
    } else {
        return {};
    }
    return parseYoloTensor(buffer.data(), dims, meta, config);
}
