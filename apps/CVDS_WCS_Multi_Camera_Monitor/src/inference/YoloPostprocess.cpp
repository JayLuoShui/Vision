#include "inference/YoloPostprocess.h"

#include <algorithm>
#include <cmath>

namespace {
struct Candidate {
    cv::Rect2f box;
    float score = 0.0f;
    int classId = -1;
};

float safeValue(float value) {
    if (std::isfinite(value)) return value;
    return 0.0f;
}

float boxIou(const cv::Rect2f& a, const cv::Rect2f& b) {
    const float x1 = std::max(a.x, b.x);
    const float y1 = std::max(a.y, b.y);
    const float x2 = std::min(a.x + a.width, b.x + b.width);
    const float y2 = std::min(a.y + a.height, b.y + b.height);
    const float interW = std::max(0.0f, x2 - x1);
    const float interH = std::max(0.0f, y2 - y1);
    const float inter = interW * interH;
    const float areaA = std::max(0.0f, a.width) * std::max(0.0f, a.height);
    const float areaB = std::max(0.0f, b.width) * std::max(0.0f, b.height);
    const float denom = areaA + areaB - inter;
    return denom <= 1e-6f ? 0.0f : inter / denom;
}

cv::Rect2f xywhToRect(float cx, float cy, float w, float h, const LetterBoxInfo& meta) {
    if (std::max({std::fabs(cx), std::fabs(cy), std::fabs(w), std::fabs(h)}) <= 2.0f) {
        cx *= static_cast<float>(meta.inputWidth);
        w *= static_cast<float>(meta.inputWidth);
        cy *= static_cast<float>(meta.inputHeight);
        h *= static_cast<float>(meta.inputHeight);
    }
    return {cx - w * 0.5f, cy - h * 0.5f, w, h};
}

DetectionResults nms(const std::vector<Candidate>& candidates, const YoloPostprocessConfig& config) {
    std::vector<int> order(candidates.size());
    for (int i = 0; i < static_cast<int>(order.size()); ++i) order[i] = i;
    std::sort(order.begin(), order.end(), [&](int lhs, int rhs) {
        return candidates[lhs].score > candidates[rhs].score;
    });

    std::vector<bool> suppressed(candidates.size(), false);
    DetectionResults results;
    for (int i = 0; i < static_cast<int>(order.size()); ++i) {
        const int idx = order[i];
        if (suppressed[idx]) continue;
        const Candidate& keep = candidates[idx];
        DetectionResult det;
        det.classId = keep.classId;
        det.className = QString("class_%1").arg(keep.classId);
        det.confidence = keep.score;
        det.box = keep.box;
        results.push_back(det);

        for (int j = i + 1; j < static_cast<int>(order.size()); ++j) {
            const int otherIdx = order[j];
            if (suppressed[otherIdx]) continue;
            const Candidate& other = candidates[otherIdx];
            if (other.classId != keep.classId) continue;
            if (boxIou(keep.box, other.box) > config.iou) suppressed[otherIdx] = true;
        }
    }
    return results;
}
}  // namespace

DetectionResults parseYoloTensor(const float* data, const std::vector<size_t>& shape, const LetterBoxInfo& meta, const YoloPostprocessConfig& config) {
    if (data == nullptr || shape.empty()) return {};

    std::vector<size_t> dims;
    dims.reserve(shape.size());
    for (size_t dim : shape) {
        if (!(dims.empty() && dim == 1)) dims.push_back(dim);
    }
    if (dims.size() < 2) return {};

    bool attrMajor = false;
    size_t candidates = 0;
    size_t attrs = 0;

    if (dims.size() == 2) {
        const size_t d0 = dims[0];
        const size_t d1 = dims[1];
        if (d0 <= 512 && d1 > d0) {
            attrMajor = true;   // [attrs, candidates], common YOLOv8 export: [84, 8400]
            attrs = d0;
            candidates = d1;
        } else {
            attrMajor = false;  // [candidates, attrs], common YOLOv5 export: [25200, 85]
            candidates = d0;
            attrs = d1;
        }
    } else {
        // Fall back to treating the last dimension as attributes and flattening preceding dimensions.
        attrs = dims.back();
        candidates = 1;
        for (size_t i = 0; i + 1 < dims.size(); ++i) candidates *= dims[i];
        attrMajor = false;
    }

    if (candidates == 0 || attrs < 5) return {};

    const auto at = [&](size_t candidate, size_t attr) -> float {
        if (attrMajor) return safeValue(data[attr * candidates + candidate]);
        return safeValue(data[candidate * attrs + attr]);
    };

    const bool yoloV5LikeObjectness = (attrs == 6 || attrs == 85);
    const int classStart = yoloV5LikeObjectness ? 5 : 4;
    const int classCount = static_cast<int>(attrs) - classStart;
    if (classCount <= 0) return {};

    std::vector<Candidate> candidatesOut;
    candidatesOut.reserve(std::min<size_t>(candidates, 1024));

    for (size_t i = 0; i < candidates; ++i) {
        int classId = 0;
        float bestClassScore = at(i, static_cast<size_t>(classStart));
        for (int c = 1; c < classCount; ++c) {
            const float score = at(i, static_cast<size_t>(classStart + c));
            if (score > bestClassScore) {
                bestClassScore = score;
                classId = c;
            }
        }

        if (config.classFilterId >= 0 && classId != config.classFilterId) continue;
        const float objectness = yoloV5LikeObjectness ? at(i, 4) : 1.0f;
        const float score = objectness * bestClassScore;
        if (score < config.confidence) continue;

        const float cx = at(i, 0);
        const float cy = at(i, 1);
        const float w = at(i, 2);
        const float h = at(i, 3);
        if (w <= 1e-3f || h <= 1e-3f) continue;

        const cv::Rect2f letterboxRect = xywhToRect(cx, cy, w, h, meta);
        const cv::Rect2f originalRect = mapBoxToOriginal(letterboxRect, meta);
        if (originalRect.width <= 1.0f || originalRect.height <= 1.0f) continue;

        candidatesOut.push_back({originalRect, score, classId});
    }

    return nms(candidatesOut, config);
}
