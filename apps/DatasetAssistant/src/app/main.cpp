#include "app/MainWindow.h"
#include "core/BatchProcessor.h"
#include "core/DatasetSplitter.h"
#include "core/InferenceEngine.h"
#include "core/ProjectManager.h"
#include "core/RuntimePaths.h"

#include <QApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QtGlobal>

#include <opencv2/core/version.hpp>

#include <filesystem>
#include <iostream>

namespace {

int printCliError(const QString& message, int code) {
    QJsonObject json;
    json["ok"] = false;
    json["error"] = message;
    std::cout << QJsonDocument(json).toJson(QJsonDocument::Compact).toStdString() << std::endl;
    return code;
}

bool projectFileReady(const QString& projectPath) {
    if (projectPath.isEmpty()) {
        return false;
    }
    std::error_code error;
    return std::filesystem::is_regular_file(projectPath.toStdString(), error);
}

int printDiagnose() {
    InferenceEngine engine;
    GpuDiagnostic gpu = engine.diagnoseGpu();
    QJsonObject json;
    json["app_version"] = QString::fromStdString(RuntimePaths::version());
    json["qt_version"] = QT_VERSION_STR;
    json["opencv_version"] = CV_VERSION;
    json["onnxruntime_version"] = "configured-at-build";
    json["cuda_provider_available"] = gpu.cudaProviderAvailable;
    json["cpu_provider_available"] = gpu.cpuProviderAvailable;
    json["gpu_name"] = QString::fromStdString(gpu.gpuName);
    json["user_data_dir"] = QString::fromStdString(RuntimePaths::userDataDir().string());
    json["log_dir"] = QString::fromStdString(RuntimePaths::logDir().string());
    json["writable_output_test"] = RuntimePaths::isWritableDirectory(RuntimePaths::defaultOutputDir());
    std::cout << QJsonDocument(json).toJson(QJsonDocument::Compact).toStdString() << std::endl;
    return 0;
}

QString valueAfter(const QStringList& args, const QString& flag) {
    const int index = args.indexOf(flag);
    if (index >= 0 && index + 1 < args.size()) {
        return args[index + 1];
    }
    return {};
}

int runBatchProcess(const QString& projectPath) {
    if (projectPath.isEmpty()) {
        return printCliError("missing project file", 2);
    }
    if (!projectFileReady(projectPath)) {
        return printCliError("project file not found: " + projectPath, 2);
    }
    ProjectConfig config = ProjectManager::load(projectPath.toStdString());
    BatchProcessSummary summary = BatchProcessor::processImages(config);
    QJsonObject json;
    json["ok"] = summary.failedItems == 0;
    json["processed_images"] = summary.processedImages;
    json["failed_items"] = summary.failedItems;
    json["output_dir"] = QString::fromStdString((config.outputDir / "processed").string());
    std::cout << QJsonDocument(json).toJson(QJsonDocument::Compact).toStdString() << std::endl;
    return summary.failedItems == 0 ? 0 : 1;
}

int runSplitDataset(const QString& projectPath) {
    if (projectPath.isEmpty()) {
        return printCliError("missing project file", 2);
    }
    if (!projectFileReady(projectPath)) {
        return printCliError("project file not found: " + projectPath, 2);
    }
    ProjectConfig config = ProjectManager::load(projectPath.toStdString());
    config.split.sourceAnnotationFormat = config.annotationFormat;
    if (config.split.classNames.empty()) {
        config.split.classNames = config.classNames;
    }
    SplitResult split = DatasetSplitter::splitFiles(config.imageInputDir, config.annotationDir, config.split);
    std::string folder = "dataset_yolo";
    if (config.split.format == DatasetFormat::Coco) {
        folder = "dataset_coco";
    } else if (config.split.format == DatasetFormat::Voc) {
        folder = "dataset_voc";
    } else if (config.split.format == DatasetFormat::MaskPng) {
        folder = "dataset_mask_png";
    }
    DatasetSplitter::exportDataset(split, config.outputDir / folder, config.split);
    QJsonObject json;
    json["ok"] = true;
    json["train_images"] = static_cast<int>(split.train.size());
    json["val_images"] = static_cast<int>(split.val.size());
    json["test_images"] = static_cast<int>(split.test.size());
    json["output_dir"] = QString::fromStdString((config.outputDir / folder).string());
    std::cout << QJsonDocument(json).toJson(QJsonDocument::Compact).toStdString() << std::endl;
    return 0;
}

}  // namespace

int main(int argc, char* argv[]) {
    QApplication app(argc, argv);
    QApplication::setApplicationName("数据集制作助手 V1.0");
    QApplication::setOrganizationName("CVDS");
    QApplication::setApplicationVersion(QString::fromStdString(RuntimePaths::version()));

    QStringList args = app.arguments();
    if (args.contains("--version")) {
        std::cout << RuntimePaths::version() << std::endl;
        return 0;
    }
    if (args.contains("--diagnose")) {
        return printDiagnose();
    }
    if (args.contains("--batch-process")) {
        return runBatchProcess(valueAfter(args, "--batch-process"));
    }
    if (args.contains("--split-dataset")) {
        return runSplitDataset(valueAfter(args, "--split-dataset"));
    }
    MainWindow window;
    window.show();
    return app.exec();
}
