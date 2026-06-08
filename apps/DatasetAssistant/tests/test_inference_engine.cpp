#include "core/InferenceEngine.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <vector>

namespace {

bool near(double a, double b) {
    return std::abs(a - b) < 0.01;
}

} // namespace

int main() {
    InferenceEngine engine;
    const cv::Mat emptyImage;
    assert(engine.infer(emptyImage).empty());

    InferenceConfig config;
    config.inputWidth = 640;
    config.inputHeight = 640;
    config.confidenceThreshold = 0.25f;
    config.iouThreshold = 0.45f;
    config.classNames = {"parcel", "bag"};

    // 每行格式：cx, cy, w, h, class0_score, class1_score。
    const std::vector<float> rowMajorOutput = {
        320.0f, 320.0f, 160.0f, 80.0f, 0.90f, 0.10f,
        322.0f, 318.0f, 160.0f, 80.0f, 0.80f, 0.20f,
        100.0f, 300.0f, 60.0f, 40.0f, 0.10f, 0.70f,
        500.0f, 500.0f, 50.0f, 50.0f, 0.20f, 0.10f,
    };

    const auto detections = InferenceEngine::postprocessYoloOutput(
        rowMajorOutput, YoloOutputShape{4, 6}, 1280, 720, config);
    assert(detections.size() == 2);
    assert(detections[0].classId == 0);
    assert(detections[0].className == "parcel");
    assert(near(detections[0].confidence, 0.90));
    assert(near(detections[0].box.x1, 480.0));
    assert(near(detections[0].box.y1, 280.0));
    assert(near(detections[0].box.x2, 800.0));
    assert(near(detections[0].box.y2, 440.0));
    assert(detections[1].classId == 1);
    assert(detections[1].className == "bag");

    // 常见 YOLOv8 ONNX 会输出 [channels, boxes]，这里验证转置形状也能解析。
    std::vector<float> transposedOutput;
    for (int c = 0; c < 6; ++c) {
        for (int r = 0; r < 4; ++r) {
            transposedOutput.push_back(rowMajorOutput[static_cast<size_t>(r * 6 + c)]);
        }
    }
    const auto transposedDetections = InferenceEngine::postprocessYoloOutput(
        transposedOutput, YoloOutputShape{6, 4}, 1280, 720, config);
    assert(transposedDetections.size() == 2);
    assert(transposedDetections[0].classId == 0);
    assert(transposedDetections[1].classId == 1);

    std::vector<float> wideTransposedOutput;
    for (int c = 0; c < 6; ++c) {
        for (int r = 0; r < 8; ++r) {
            const int sourceRow = r % 4;
            wideTransposedOutput.push_back(rowMajorOutput[static_cast<size_t>(sourceRow * 6 + c)]);
        }
    }
    const auto wideTransposedDetections = InferenceEngine::postprocessYoloOutput(
        wideTransposedOutput, YoloOutputShape{6, 8}, 1280, 720, config);
    assert(wideTransposedDetections.size() == 2);
    assert(wideTransposedDetections[0].classId == 0);

    std::cout << "test_inference_engine passed\n";
    return 0;
}
