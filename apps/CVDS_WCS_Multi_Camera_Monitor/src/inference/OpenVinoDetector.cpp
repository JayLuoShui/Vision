#include "inference/OpenVinoDetector.h"

#include <QDir>
#include <QFileInfo>
#include <opencv2/imgproc.hpp>

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
        const QString ovDevice = device.trimmed().isEmpty() ? "AUTO" : device.trimmed().toUpper();
        compiledModel_ = core_.compile_model(model, ovDevice.toStdString());
        inferRequest_ = compiledModel_.create_infer_request();
        loaded_ = true;
        return true;
    } catch (const std::exception& ex) {
        loaded_ = false;
        if (error) *error = QString::fromUtf8(ex.what());
        return false;
    }
}

DetectionResults OpenVinoDetector::infer(const cv::Mat& frame, float, float, int, QString* error) {
    if (!loaded_) {
        if (error) *error = "OpenVINO detector is not loaded";
        return {};
    }
    if (frame.empty()) return {};
    return {};
}

DetectionResults OpenVinoDetector::parseOutput(const ov::Tensor&, const LetterBoxInfo&, const YoloPostprocessConfig&) const {
    return {};
}
