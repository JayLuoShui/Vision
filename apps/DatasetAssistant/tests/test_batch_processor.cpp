#include "core/AnnotationIO.h"
#include "core/BatchProcessor.h"
#include "core/ProjectManager.h"

#include <opencv2/imgcodecs.hpp>

#include <cassert>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

int main() {
    const fs::path root = fs::temp_directory_path() / "dataset_assistant_batch_test";
    fs::remove_all(root);
    fs::create_directories(root / "images");
    fs::create_directories(root / "labels");

    cv::Mat image(10, 20, CV_8UC3, cv::Scalar(10, 20, 30));
    assert(cv::imwrite((root / "images" / "a.jpg").string(), image));
    {
        std::ofstream label(root / "labels" / "a.txt");
        label << "0 0.500000 0.500000 0.500000 0.400000\n";
    }

    ProjectConfig config = ProjectManager::createDefault(root / "project.cvdsproj.json");
    config.imageInputDir = root / "images";
    config.annotationDir = root / "labels";
    config.outputDir = root / "out";
    config.classNames = {"box"};
    config.split.classNames = config.classNames;
    config.transform.enableResize = true;
    config.transform.resize.width = 40;
    config.transform.resize.height = 20;
    config.transform.rename.prefix = "sample_";
    config.transform.rename.startIndex = 7;
    config.transform.rename.digits = 3;
    config.transform.rename.outputExtension = ".jpg";

    assert(ProjectManager::save(config, config.projectFile));
    ProjectConfig loaded = ProjectManager::load(config.projectFile);
    BatchProcessSummary summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 1);
    assert(summary.failedItems == 0);

    const fs::path outImage = root / "out" / "processed" / "images" / "sample_007.jpg";
    const fs::path outLabel = root / "out" / "processed" / "labels" / "sample_007.txt";
    assert(fs::exists(outImage));
    assert(fs::exists(outLabel));
    assert(fs::exists(root / "out" / "processed" / "summary.json"));
    assert(fs::exists(root / "out" / "processed" / "task_manifest.json"));

    cv::Mat output = cv::imread(outImage.string(), cv::IMREAD_COLOR);
    assert(output.cols == 40);
    assert(output.rows == 20);

    ImageAnnotation ann = AnnotationIO::loadYolo(outLabel, outImage, 40, 20, loaded.classNames);
    assert(ann.objects.size() == 1);
    assert(std::abs(ann.objects[0].box.x1 - 10.0) < 0.01);
    assert(std::abs(ann.objects[0].box.x2 - 30.0) < 0.01);
    assert(std::abs(ann.objects[0].box.y1 - 6.0) < 0.01);
    assert(std::abs(ann.objects[0].box.y2 - 14.0) < 0.01);

    auto lastWrite = fs::last_write_time(outImage);
    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 0);
    assert(summary.skippedImages == 1);
    assert(fs::last_write_time(outImage) == lastWrite);

    loaded.outputAnnotationFormat = AnnotationFormat::Voc;
    loaded.outputDir = root / "out_voc";
    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 1);
    const fs::path vocLabel = root / "out_voc" / "processed" / "labels" / "sample_007.xml";
    assert(fs::exists(vocLabel));
    {
        std::ifstream xml(vocLabel);
        std::string text((std::istreambuf_iterator<char>(xml)), std::istreambuf_iterator<char>());
        assert(text.find("<name>box</name>") != std::string::npos);
    }
    loaded.classNames = {"parcel"};
    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 1);
    assert(summary.skippedImages == 0);
    {
        std::ifstream xml(vocLabel);
        std::string text((std::istreambuf_iterator<char>(xml)), std::istreambuf_iterator<char>());
        assert(text.find("<name>parcel</name>") != std::string::npos);
    }
    loaded.classNames = {"box"};

    loaded.outputAnnotationFormat = AnnotationFormat::Coco;
    loaded.outputDir = root / "out_coco";
    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 1);
    const fs::path cocoInstances = root / "out_coco" / "processed" / "annotations" / "instances.json";
    assert(fs::exists(cocoInstances));
    auto cocoRoundTrip = AnnotationIO::loadCoco(cocoInstances, loaded.classNames);
    assert(cocoRoundTrip.size() == 1);
    assert(cocoRoundTrip[0].objects.size() == 1);

    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 0);
    assert(summary.skippedImages == 1);
    cocoRoundTrip = AnnotationIO::loadCoco(cocoInstances, loaded.classNames);
    assert(cocoRoundTrip.size() == 1);
    assert(cocoRoundTrip[0].objects.size() == 1);

    fs::remove(cocoInstances);
    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 1);
    assert(summary.skippedImages == 0);
    cocoRoundTrip = AnnotationIO::loadCoco(cocoInstances, loaded.classNames);
    assert(cocoRoundTrip.size() == 1);
    assert(cocoRoundTrip[0].objects.size() == 1);

    loaded.outputAnnotationFormat = AnnotationFormat::MaskPng;
    loaded.outputDir = root / "out_mask";
    summary = BatchProcessor::processImages(loaded);
    assert(summary.processedImages == 1);
    const fs::path maskPath = root / "out_mask" / "processed" / "labels" / "sample_007.png";
    assert(fs::exists(maskPath));
    cv::Mat mask = cv::imread(maskPath.string(), cv::IMREAD_UNCHANGED);
    assert(!mask.empty());
    assert(mask.at<uchar>(10, 20) == 1);

    fs::create_directories(root / "coco_images");
    fs::create_directories(root / "coco_ann");
    assert(cv::imwrite((root / "coco_images" / "coco_a.jpg").string(), image));
    {
        std::ofstream coco(root / "coco_ann" / "instances.json");
        coco << "{\"images\":[{\"id\":1,\"file_name\":\"coco_a.jpg\",\"width\":20,\"height\":10}],"
             << "\"annotations\":[{\"id\":1,\"image_id\":1,\"category_id\":1,\"bbox\":[4,2,8,4],\"area\":32,\"iscrowd\":0}],"
             << "\"categories\":[{\"id\":1,\"name\":\"box\"}]}\n";
    }
    ProjectConfig cocoConfig = loaded;
    cocoConfig.imageInputDir = root / "coco_images";
    cocoConfig.annotationDir = root / "coco_ann";
    cocoConfig.annotationFormat = AnnotationFormat::Coco;
    cocoConfig.outputAnnotationFormat = AnnotationFormat::Yolo;
    cocoConfig.outputDir = root / "out_from_coco";
    cocoConfig.transform.enableResize = false;
    summary = BatchProcessor::processImages(cocoConfig);
    assert(summary.processedImages == 1);
    ImageAnnotation cocoOut = AnnotationIO::loadYolo(
        root / "out_from_coco" / "processed" / "labels" / "sample_007.txt",
        root / "out_from_coco" / "processed" / "images" / "sample_007.jpg",
        20,
        10,
        cocoConfig.classNames
    );
    assert(cocoOut.objects.size() == 1);
    assert(std::abs(cocoOut.objects[0].box.x1 - 4.0) < 0.01);
    assert(std::abs(cocoOut.objects[0].box.y1 - 2.0) < 0.01);
    assert(std::abs(cocoOut.objects[0].box.x2 - 12.0) < 0.01);
    assert(std::abs(cocoOut.objects[0].box.y2 - 6.0) < 0.01);

    fs::create_directories(root / "mask_images");
    fs::create_directories(root / "mask_labels");
    assert(cv::imwrite((root / "mask_images" / "mask_a.jpg").string(), image));
    cv::Mat inputMask = cv::Mat::zeros(10, 20, CV_8UC1);
    inputMask(cv::Rect(5, 3, 6, 4)).setTo(1);
    assert(cv::imwrite((root / "mask_labels" / "mask_a.png").string(), inputMask));
    ProjectConfig maskConfig = loaded;
    maskConfig.imageInputDir = root / "mask_images";
    maskConfig.annotationDir = root / "mask_labels";
    maskConfig.annotationFormat = AnnotationFormat::MaskPng;
    maskConfig.outputAnnotationFormat = AnnotationFormat::Yolo;
    maskConfig.outputDir = root / "out_from_mask";
    maskConfig.transform.enableResize = false;
    summary = BatchProcessor::processImages(maskConfig);
    assert(summary.processedImages == 1);
    ImageAnnotation maskOut = AnnotationIO::loadYolo(
        root / "out_from_mask" / "processed" / "labels" / "sample_007.txt",
        root / "out_from_mask" / "processed" / "images" / "sample_007.jpg",
        20,
        10,
        maskConfig.classNames
    );
    assert(maskOut.objects.size() == 1);
    assert(std::abs(maskOut.objects[0].box.x1 - 5.0) < 0.01);
    assert(std::abs(maskOut.objects[0].box.y1 - 3.0) < 0.01);
    assert(std::abs(maskOut.objects[0].box.x2 - 11.0) < 0.01);
    assert(std::abs(maskOut.objects[0].box.y2 - 7.0) < 0.01);

    fs::create_directories(root / "segment_images");
    fs::create_directories(root / "segment_labels");
    assert(cv::imwrite((root / "segment_images" / "seg_a.jpg").string(), image));
    {
        std::ofstream segment(root / "segment_labels" / "seg_a.txt");
        segment << "0 0.250000 0.200000 0.750000 0.200000 0.750000 0.800000 0.250000 0.800000\n";
    }
    ProjectConfig segmentConfig = loaded;
    segmentConfig.imageInputDir = root / "segment_images";
    segmentConfig.annotationDir = root / "segment_labels";
    segmentConfig.annotationFormat = AnnotationFormat::Yolo;
    segmentConfig.outputAnnotationFormat = AnnotationFormat::Yolo;
    segmentConfig.outputDir = root / "out_segment";
    segmentConfig.transform.enableResize = false;
    summary = BatchProcessor::processImages(segmentConfig);
    assert(summary.processedImages == 1);
    ImageAnnotation segmentOut = AnnotationIO::loadYolo(
        root / "out_segment" / "processed" / "labels" / "sample_007.txt",
        root / "out_segment" / "processed" / "images" / "sample_007.jpg",
        20,
        10,
        segmentConfig.classNames
    );
    assert(segmentOut.objects.size() == 1);
    assert(segmentOut.objects[0].hasPolygon);
    assert(segmentOut.objects[0].polygons[0].points.size() == 4);

    ProjectConfig cropConfig = ProjectManager::createDefault(root / "crop_project.cvdsproj.json");
    cropConfig.imageInputDir = root / "images";
    cropConfig.annotationDir = root / "labels";
    cropConfig.outputDir = root / "out_crop";
    cropConfig.classNames = {"box"};
    cropConfig.transform.rename.prefix = "crop_";
    cropConfig.transform.rename.startIndex = 1;
    cropConfig.transform.rename.digits = 2;
    cropConfig.transform.rename.outputExtension = ".jpg";
    cropConfig.transform.resize.paddingColor = cv::Scalar(7, 8, 9);
    cropConfig.transform.enableCrop = true;
    cropConfig.transform.crop.x = 6;
    cropConfig.transform.crop.y = 2;
    cropConfig.transform.crop.width = 8;
    cropConfig.transform.crop.height = 6;
    cropConfig.transform.crop.keepVisibleRatio = 0.2;
    cropConfig.transform.enableBrightnessContrast = true;
    cropConfig.transform.brightness = 12.0;
    cropConfig.transform.contrast = 1.25;
    cropConfig.transform.tile.padEdges = true;
    cropConfig.transform.tile.keepVisibleRatio = 0.35;
    cropConfig.transform.rename.jpegQuality = 88;
    assert(ProjectManager::save(cropConfig, cropConfig.projectFile));
    ProjectConfig loadedCrop = ProjectManager::load(cropConfig.projectFile);
    assert(static_cast<int>(loadedCrop.transform.resize.paddingColor[0]) == 7);
    assert(static_cast<int>(loadedCrop.transform.resize.paddingColor[1]) == 8);
    assert(static_cast<int>(loadedCrop.transform.resize.paddingColor[2]) == 9);
    assert(loadedCrop.transform.enableBrightnessContrast);
    assert(std::abs(loadedCrop.transform.brightness - 12.0) < 0.01);
    assert(std::abs(loadedCrop.transform.contrast - 1.25) < 0.01);
    assert(loadedCrop.transform.tile.padEdges);
    assert(std::abs(loadedCrop.transform.tile.keepVisibleRatio - 0.35) < 0.01);
    assert(loadedCrop.transform.rename.jpegQuality == 88);
    summary = BatchProcessor::processImages(loadedCrop);
    assert(summary.processedImages == 1);
    const fs::path cropImage = root / "out_crop" / "processed" / "images" / "crop_01.jpg";
    const fs::path cropLabel = root / "out_crop" / "processed" / "labels" / "crop_01.txt";
    cv::Mat cropped = cv::imread(cropImage.string(), cv::IMREAD_COLOR);
    assert(cropped.cols == 8);
    assert(cropped.rows == 6);
    ImageAnnotation cropOut = AnnotationIO::loadYolo(cropLabel, cropImage, 8, 6, cropConfig.classNames);
    assert(cropOut.objects.size() == 1);
    assert(std::abs(cropOut.objects[0].box.x1 - 0.0) < 0.01);
    assert(std::abs(cropOut.objects[0].box.y1 - 1.0) < 0.01);
    assert(std::abs(cropOut.objects[0].box.x2 - 8.0) < 0.01);
    assert(std::abs(cropOut.objects[0].box.y2 - 5.0) < 0.01);

    ProjectConfig fullConfig = ProjectManager::createDefault(root / "full_project.cvdsproj.json");
    fullConfig.inference.modelPath = root / "models" / "parcel.onnx";
    fullConfig.inference.namesPath = root / "models" / "names.txt";
    fullConfig.inference.classNames = {"box", "bag"};
    fullConfig.inference.devicePolicy = DevicePolicy::Gpu;
    fullConfig.inference.inputWidth = 512;
    fullConfig.inference.inputHeight = 384;
    fullConfig.inference.confidenceThreshold = 0.31f;
    fullConfig.inference.iouThreshold = 0.52f;
    assert(ProjectManager::save(fullConfig, fullConfig.projectFile));
    ProjectConfig loadedFull = ProjectManager::load(fullConfig.projectFile);
    assert(loadedFull.inference.modelPath == fullConfig.inference.modelPath);
    assert(loadedFull.inference.namesPath == fullConfig.inference.namesPath);
    assert(loadedFull.inference.classNames.size() == 2);
    assert(loadedFull.inference.classNames[1] == "bag");
    assert(loadedFull.inference.devicePolicy == DevicePolicy::Gpu);
    assert(loadedFull.inference.inputWidth == 512);
    assert(loadedFull.inference.inputHeight == 384);
    assert(std::abs(loadedFull.inference.confidenceThreshold - 0.31f) < 0.001f);
    assert(std::abs(loadedFull.inference.iouThreshold - 0.52f) < 0.001f);

    fs::create_directories(root / "tile_images");
    fs::create_directories(root / "tile_labels");
    assert(cv::imwrite((root / "tile_images" / "tile_a.jpg").string(), image));
    {
        std::ofstream tileLabel(root / "tile_labels" / "tile_a.txt");
        tileLabel << "0 0.500000 0.500000 0.500000 0.400000\n";
    }
    ProjectConfig tileConfig = ProjectManager::createDefault(root / "tile_project.cvdsproj.json");
    tileConfig.imageInputDir = root / "tile_images";
    tileConfig.annotationDir = root / "tile_labels";
    tileConfig.outputDir = root / "out_tile";
    tileConfig.classNames = {"box"};
    tileConfig.transform.enableTiling = true;
    tileConfig.transform.tile.tileWidth = 10;
    tileConfig.transform.tile.tileHeight = 10;
    tileConfig.transform.tile.overlapX = 0;
    tileConfig.transform.tile.overlapY = 0;
    tileConfig.transform.tile.padEdges = false;
    tileConfig.transform.rename.prefix = "tile_";
    tileConfig.transform.rename.startIndex = 1;
    tileConfig.transform.rename.digits = 2;
    tileConfig.transform.rename.outputExtension = ".jpg";
    summary = BatchProcessor::processImages(tileConfig);
    assert(summary.processedImages == 2);
    assert(summary.skippedImages == 0);
    const fs::path tileImage0 = root / "out_tile" / "processed" / "images" / "tile_01_tile_0.jpg";
    const fs::path tileImage1 = root / "out_tile" / "processed" / "images" / "tile_01_tile_1.jpg";
    const fs::path tileLabel1 = root / "out_tile" / "processed" / "labels" / "tile_01_tile_1.txt";
    assert(fs::exists(tileImage0));
    assert(fs::exists(tileImage1));
    assert(fs::exists(tileLabel1));
    fs::remove(tileImage1);
    fs::remove(tileLabel1);
    summary = BatchProcessor::processImages(tileConfig);
    assert(summary.processedImages == 2);
    assert(summary.skippedImages == 0);
    assert(fs::exists(tileImage1));
    assert(fs::exists(tileLabel1));

    fs::create_directories(root / "bad_images");
    {
        std::ofstream bad(root / "bad_images" / "bad.jpg");
        bad << "not an image";
    }
    ProjectConfig badConfig = ProjectManager::createDefault(root / "bad_project.cvdsproj.json");
    badConfig.imageInputDir = root / "bad_images";
    badConfig.annotationDir = root / "labels";
    badConfig.outputDir = root / "out_bad";
    summary = BatchProcessor::processImages(badConfig);
    assert(summary.processedImages == 0);
    assert(summary.failedItems == 1);
    const fs::path failedCsv = root / "out_bad" / "processed" / "failed_items.csv";
    assert(fs::exists(failedCsv));
    {
        std::ifstream failed(failedCsv);
        std::string text((std::istreambuf_iterator<char>(failed)), std::istreambuf_iterator<char>());
        assert(text.find("source,error") != std::string::npos);
        assert(text.find("bad.jpg") != std::string::npos);
        assert(text.find("failed to read image") != std::string::npos);
    }

    fs::remove_all(root);
    return 0;
}
