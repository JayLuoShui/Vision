#include "core/AnnotationIO.h"

#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;

int main() {
    const fs::path root = fs::temp_directory_path() / "dataset_assistant_io_test";
    fs::remove_all(root);
    fs::create_directories(root);

    ImageAnnotation ann;
    ann.imagePath = root / "img001.jpg";
    ann.width = 100;
    ann.height = 50;
    AnnotationObject obj;
    obj.classId = 0;
    obj.className = "parcel";
    obj.box = {10, 10, 40, 30};
    obj.polygons.push_back({{{10, 10}, {40, 10}, {40, 30}, {10, 30}}});
    obj.hasPolygon = true;
    ann.objects.push_back(obj);

    std::vector<std::string> names = {"parcel"};
    AnnotationIO::saveYolo(ann, root / "img001.txt", names, true);
    ImageAnnotation loaded = AnnotationIO::loadYolo(root / "img001.txt", ann.imagePath, 100, 50, names);
    assert(loaded.objects.size() == 1);
    assert(loaded.objects.at(0).hasPolygon);
    assert(loaded.objects.at(0).polygons.at(0).points.size() == 4);

    {
        std::ofstream bad(root / "bad.txt");
        bad << "0 0.5 nope 0.1 0.1\n";
        bad << "0 1.2 0.5 0.1 0.1\n";
        bad << "0 0.5 0.5 -0.1 0.1\n";
        bad << "0 0.1 0.1 1.2 0.1 0.2 0.2\n";
    }
    ImageAnnotation bad = AnnotationIO::loadYolo(root / "bad.txt", root / "bad.jpg", 100, 50, names);
    assert(bad.objects.empty());

    {
        std::ofstream bom(root / "bom.txt", std::ios::binary);
        bom << "\xEF\xBB\xBF";
        bom << "0 0.5 0.5 0.2 0.2\n";
    }
    ImageAnnotation bom = AnnotationIO::loadYolo(root / "bom.txt", root / "bom.jpg", 100, 50, names);
    assert(bom.objects.size() == 1);

    AnnotationIO::saveVoc(ann, root / "img001.xml");
    ImageAnnotation voc = AnnotationIO::loadVoc(root / "img001.xml", names);
    assert(voc.objects.size() == 1);
    assert(voc.objects.at(0).className == "parcel");

    AnnotationIO::saveCoco({ann}, root / "instances.json", names);
    auto coco = AnnotationIO::loadCoco(root / "instances.json", names);
    assert(coco.size() == 1);
    assert(coco.at(0).objects.size() == 1);
    assert(coco.at(0).objects.at(0).hasPolygon);
    assert(coco.at(0).objects.at(0).polygons.at(0).points.size() == 4);
    assert(std::abs(coco.at(0).objects.at(0).polygons.at(0).points.at(2).x - 40.0) < 0.01);

    {
        std::ofstream custom(root / "custom_ids.json");
        custom << "{\"images\":[{\"id\":3,\"file_name\":\"custom.jpg\",\"width\":100,\"height\":50}],"
               << "\"annotations\":[{\"id\":9,\"image_id\":3,\"category_id\":7,\"bbox\":[1,2,10,20],\"area\":200,\"iscrowd\":0}],"
               << "\"categories\":[{\"id\":7,\"name\":\"parcel\"}]}\n";
    }
    auto customCoco = AnnotationIO::loadCoco(root / "custom_ids.json", names);
    assert(customCoco.size() == 1);
    assert(customCoco.at(0).objects.size() == 1);
    assert(customCoco.at(0).objects.at(0).classId == 0);
    assert(customCoco.at(0).objects.at(0).className == "parcel");

    cv::Mat mask = cv::Mat::zeros(10, 12, CV_8UC1);
    mask(cv::Rect(2, 3, 4, 5)).setTo(1);
    AnnotationIO::saveMaskPng(mask, root / "mask.png", root / "mask.json", names);
    cv::Mat loadedMask = AnnotationIO::loadMaskPng(root / "mask.png");
    assert(loadedMask.rows == 10 && loadedMask.cols == 12);
    assert(loadedMask.at<uchar>(4, 3) == 1);

    fs::remove_all(root);
    std::cout << "test_annotation_io passed\n";
    return 0;
}
