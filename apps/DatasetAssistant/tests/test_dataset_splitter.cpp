#include "core/DatasetSplitter.h"
#include "core/AnnotationIO.h"

#include <opencv2/imgcodecs.hpp>

#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>

namespace fs = std::filesystem;

int main() {
    const fs::path root = fs::temp_directory_path() / "dataset_assistant_split_test";
    fs::remove_all(root);
    fs::create_directories(root / "images");
    fs::create_directories(root / "labels");
    for (int i = 0; i < 10; ++i) {
        cv::Mat image(20, 30, CV_8UC3, cv::Scalar(20 + i, 30, 40));
        assert(cv::imwrite((root / "images" / ("img" + std::to_string(i) + ".jpg")).string(), image));
        std::ofstream(root / "labels" / ("img" + std::to_string(i) + ".txt")) << (i % 2 == 0 ? "0 0.5 0.5 0.2 0.2\n" : "");
    }

    SplitConfig config;
    config.trainRatio = 0.7;
    config.valRatio = 0.2;
    config.testRatio = 0.1;
    config.seed = 1234;
    config.includeNegative = true;
    config.format = DatasetFormat::Yolo;
    config.classNames = {"parcel"};

    auto first = DatasetSplitter::splitFiles(root / "images", root / "labels", config);
    auto second = DatasetSplitter::splitFiles(root / "images", root / "labels", config);
    assert(first.train.size() == 7);
    assert(first.val.size() == 2);
    assert(first.test.size() == 1);
    assert(first.train.at(0).imagePath == second.train.at(0).imagePath);

    fs::create_directories(root / "uppercase_images");
    fs::create_directories(root / "uppercase_labels");
    cv::Mat uppercaseImage(12, 16, CV_8UC3, cv::Scalar(80, 90, 100));
    assert(cv::imwrite((root / "uppercase_images" / "upper.JPG").string(), uppercaseImage));
    std::ofstream(root / "uppercase_labels" / "upper.txt") << "0 0.5 0.5 0.5 0.5\n";
    SplitConfig uppercaseConfig = config;
    uppercaseConfig.trainRatio = 1.0;
    uppercaseConfig.valRatio = 0.0;
    uppercaseConfig.testRatio = 0.0;
    auto uppercaseSplit = DatasetSplitter::splitFiles(root / "uppercase_images", root / "uppercase_labels", uppercaseConfig);
    assert(uppercaseSplit.train.size() == 1);

    fs::create_directories(root / "invalid_label_images");
    fs::create_directories(root / "invalid_label_labels");
    assert(cv::imwrite((root / "invalid_label_images" / "invalid.jpg").string(), uppercaseImage));
    std::ofstream(root / "invalid_label_labels" / "invalid.txt") << "0 1.5 0.5 0.2 0.2\n";
    SplitConfig annotatedOnlyConfig = config;
    annotatedOnlyConfig.includeNegative = false;
    annotatedOnlyConfig.trainRatio = 1.0;
    annotatedOnlyConfig.valRatio = 0.0;
    annotatedOnlyConfig.testRatio = 0.0;
    auto invalidLabelSplit = DatasetSplitter::splitFiles(root / "invalid_label_images", root / "invalid_label_labels", annotatedOnlyConfig);
    assert(invalidLabelSplit.train.empty());

    const fs::path output = root / "out";
    DatasetSplitter::exportYolo(first, output, config);
    assert(fs::exists(output / "images" / "train"));
    assert(fs::exists(output / "labels" / "train"));
    assert(fs::exists(output / "data.yaml"));
    assert(fs::exists(output / "summary.json"));
    {
        std::ifstream yamlFile(output / "data.yaml");
        std::stringstream buffer;
        buffer << yamlFile.rdbuf();
        const std::string yaml = buffer.str();
        assert(yaml.find("path: ") != std::string::npos);
        assert(yaml.find('\\') == std::string::npos);
        assert(yaml.find("train: images/train") != std::string::npos);
    }
    {
        std::ifstream summaryFile(output / "summary.json");
        std::stringstream buffer;
        buffer << summaryFile.rdbuf();
        const std::string summary = buffer.str();
        assert(summary.find("\"class_distribution\"") != std::string::npos);
        assert(summary.find("\"parcel\"") != std::string::npos);
        assert(summary.find("\"total\": 5") != std::string::npos);
        assert(summary.find("\"train_ratio\": 0.7") != std::string::npos);
        assert(summary.find("\"seed\": 1234") != std::string::npos);
    }

    config.format = DatasetFormat::Voc;
    const fs::path vocOutput = root / "out_voc";
    DatasetSplitter::exportDataset(first, vocOutput, config);
    assert(fs::exists(vocOutput / "train" / "images"));
    assert(fs::exists(vocOutput / "train" / "annotations"));
    assert(fs::exists(vocOutput / "summary.json"));

    config.format = DatasetFormat::Coco;
    const fs::path cocoOutput = root / "out_coco";
    DatasetSplitter::exportDataset(first, cocoOutput, config);
    assert(fs::exists(cocoOutput / "train"));
    assert(fs::exists(cocoOutput / "annotations" / "instances_train.json"));
    assert(fs::exists(cocoOutput / "summary.json"));

    config.format = DatasetFormat::MaskPng;
    const fs::path maskOutput = root / "out_mask";
    DatasetSplitter::exportDataset(first, maskOutput, config);
    assert(fs::exists(maskOutput / "train" / "images"));
    assert(fs::exists(maskOutput / "train" / "masks"));
    assert(fs::exists(maskOutput / "summary.json"));

    SplitResult withMissingItem;
    withMissingItem.train.push_back(first.train.front());
    withMissingItem.train.push_back({root / "images" / "missing.jpg", root / "labels" / "missing.txt", false});
    const fs::path missingOutput = root / "out_missing";
    DatasetSplitter::exportYolo(withMissingItem, missingOutput, config);
    assert(fs::exists(missingOutput / "images" / "train" / first.train.front().imagePath.filename()));
    assert(fs::exists(missingOutput / "failed_items.csv"));
    {
        std::ifstream failedFile(missingOutput / "failed_items.csv");
        std::stringstream buffer;
        buffer << failedFile.rdbuf();
        const std::string failed = buffer.str();
        assert(failed.find("missing.jpg") != std::string::npos);
        assert(failed.find("copy image failed") != std::string::npos);
    }

    const fs::path vocRoot = root / "voc_source";
    fs::create_directories(vocRoot / "images");
    fs::create_directories(vocRoot / "annotations");
    cv::Mat vocImage(50, 100, CV_8UC3, cv::Scalar(10, 20, 30));
    assert(cv::imwrite((vocRoot / "images" / "parcel.jpg").string(), vocImage));
    {
        std::ofstream xml(vocRoot / "annotations" / "parcel.xml");
        xml << "<annotation><filename>parcel.jpg</filename><size><width>100</width><height>50</height><depth>3</depth></size>"
            << "<object><name>parcel</name><bndbox><xmin>10</xmin><ymin>5</ymin><xmax>60</xmax><ymax>30</ymax></bndbox></object>"
            << "</annotation>";
    }
    SplitConfig vocInputConfig;
    vocInputConfig.trainRatio = 1.0;
    vocInputConfig.valRatio = 0.0;
    vocInputConfig.testRatio = 0.0;
    vocInputConfig.includeNegative = false;
    vocInputConfig.format = DatasetFormat::Yolo;
    vocInputConfig.sourceAnnotationFormat = AnnotationFormat::Voc;
    vocInputConfig.classNames = {"parcel"};
    auto vocInputSplit = DatasetSplitter::splitFiles(vocRoot / "images", vocRoot / "annotations", vocInputConfig);
    assert(vocInputSplit.train.size() == 1);
    const fs::path vocToYoloOutput = root / "voc_to_yolo";
    DatasetSplitter::exportDataset(vocInputSplit, vocToYoloOutput, vocInputConfig);
    {
        std::ifstream yolo(vocToYoloOutput / "labels" / "train" / "parcel.txt");
        std::stringstream buffer;
        buffer << yolo.rdbuf();
        const std::string text = buffer.str();
        assert(text.find("0 ") == 0);
    }
    {
        std::ifstream summaryFile(vocToYoloOutput / "summary.json");
        std::stringstream buffer;
        buffer << summaryFile.rdbuf();
        const std::string summary = buffer.str();
        assert(summary.find("\"train_objects\": 1") != std::string::npos);
        assert(summary.find("\"total\": 1") != std::string::npos);
    }

    const fs::path cocoRoot = root / "coco_source";
    fs::create_directories(cocoRoot / "images");
    fs::create_directories(cocoRoot / "annotations");
    cv::Mat cocoImage(40, 80, CV_8UC3, cv::Scalar(40, 20, 10));
    assert(cv::imwrite((cocoRoot / "images" / "coco_parcel.jpg").string(), cocoImage));
    ImageAnnotation cocoAnnotation;
    cocoAnnotation.imagePath = cocoRoot / "images" / "coco_parcel.jpg";
    cocoAnnotation.width = 80;
    cocoAnnotation.height = 40;
    AnnotationObject cocoObject;
    cocoObject.classId = 0;
    cocoObject.className = "parcel";
    cocoObject.box = {8, 4, 48, 24};
    cocoObject.polygons.push_back({{{8, 4}, {48, 4}, {48, 24}, {8, 24}}});
    cocoObject.hasPolygon = true;
    cocoAnnotation.objects.push_back(cocoObject);
    AnnotationIO::saveCoco({cocoAnnotation}, cocoRoot / "annotations" / "instances.json", {"parcel"});
    SplitConfig cocoInputConfig = vocInputConfig;
    cocoInputConfig.sourceAnnotationFormat = AnnotationFormat::Coco;
    auto cocoInputSplit = DatasetSplitter::splitFiles(cocoRoot / "images", cocoRoot / "annotations", cocoInputConfig);
    assert(cocoInputSplit.train.size() == 1);
    const fs::path cocoToYoloOutput = root / "coco_to_yolo";
    DatasetSplitter::exportDataset(cocoInputSplit, cocoToYoloOutput, cocoInputConfig);
    {
        std::ifstream yolo(cocoToYoloOutput / "labels" / "train" / "coco_parcel.txt");
        std::stringstream buffer;
        buffer << yolo.rdbuf();
        const std::string text = buffer.str();
        assert(text.find("0 ") == 0);
    }
    ImageAnnotation cocoYoloSegment = AnnotationIO::loadYolo(
        cocoToYoloOutput / "labels" / "train" / "coco_parcel.txt",
        cocoToYoloOutput / "images" / "train" / "coco_parcel.jpg",
        80,
        40,
        cocoInputConfig.classNames
    );
    assert(cocoYoloSegment.objects.size() == 1);
    assert(cocoYoloSegment.objects[0].hasPolygon);
    assert(cocoYoloSegment.objects[0].polygons[0].points.size() == 4);
    {
        std::ifstream summaryFile(cocoToYoloOutput / "summary.json");
        std::stringstream buffer;
        buffer << summaryFile.rdbuf();
        const std::string summary = buffer.str();
        assert(summary.find("\"train_objects\": 1") != std::string::npos);
        assert(summary.find("\"total\": 1") != std::string::npos);
    }

    const fs::path maskRoot = root / "mask_source";
    fs::create_directories(maskRoot / "images");
    fs::create_directories(maskRoot / "annotations");
    cv::Mat maskImage(10, 20, CV_8UC3, cv::Scalar(15, 25, 35));
    assert(cv::imwrite((maskRoot / "images" / "mask_parcel.jpg").string(), maskImage));
    cv::Mat sourceMask = cv::Mat::zeros(10, 20, CV_8UC1);
    sourceMask(cv::Rect(4, 2, 6, 4)).setTo(1);
    assert(cv::imwrite((maskRoot / "annotations" / "mask_parcel.png").string(), sourceMask));
    SplitConfig maskInputConfig = vocInputConfig;
    maskInputConfig.sourceAnnotationFormat = AnnotationFormat::MaskPng;
    auto maskInputSplit = DatasetSplitter::splitFiles(maskRoot / "images", maskRoot / "annotations", maskInputConfig);
    assert(maskInputSplit.train.size() == 1);
    const fs::path maskToYoloOutput = root / "mask_to_yolo";
    DatasetSplitter::exportDataset(maskInputSplit, maskToYoloOutput, maskInputConfig);
    {
        std::ifstream yolo(maskToYoloOutput / "labels" / "train" / "mask_parcel.txt");
        std::stringstream buffer;
        buffer << yolo.rdbuf();
        const std::string text = buffer.str();
        assert(text.find("0 ") == 0);
        assert(text.find("0.35") != std::string::npos);
        assert(text.find("0.4") != std::string::npos);
    }
    {
        std::ifstream summaryFile(maskToYoloOutput / "summary.json");
        std::stringstream buffer;
        buffer << summaryFile.rdbuf();
        const std::string summary = buffer.str();
        assert(summary.find("\"train_objects\": 1") != std::string::npos);
        assert(summary.find("\"total\": 1") != std::string::npos);
    }

    fs::remove_all(root);
    std::cout << "test_dataset_splitter passed\n";
    return 0;
}
