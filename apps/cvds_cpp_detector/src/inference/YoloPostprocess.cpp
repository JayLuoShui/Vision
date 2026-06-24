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

cv::Rect2f xyxyToRect(float x1, float y1, float x2, float y2, const LetterBoxInfo& meta) {
    if (std::max({std::fabs(x1), std::fabs(y1), std::fabs(x2), std::fabs(y2)}) <= 2.0f) {
        x1 *= static_cast<float>(meta.inputWidth);
        x2 *= static_cast<float>(meta.inputWidth);
        y1 *= static_cast<float>(meta.inputHeight);
        y2 *= static_cast<float>(meta.inputHeight);
    }
    return {x1, y1, x2 - x1, y2 - y1};
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
    if (data == nullptr || shape.size() < 2 || meta.inputWidth <= 0 || meta.inputHeight <= 0) return {};

    std::vector<size_t> dims(shape.begin(), shape.end());
    while (dims.size() > 2 && dims.front() == 1) dims.erase(dims.begin());
    if (dims.size() != 2) return {};

    bool attrMajor = false;
    size_t candidates = 0;
    size_t attrs = 0;

    const size_t d0 = dims[0];
    const size_t d1 = dims[1];
    if (d1 == 6) {
        candidates = d0;
        attrs = d1;
    } else if (d0 >= 5 && d0 <= 512 && d1 > d0) {
        attrMajor = true;
        attrs = d0;
        candidates = d1;
    } else if (d1 >= 5 && d1 <= 512) {
        candidates = d0;
        attrs = d1;
    } else {
        return {};
    }

    if (candidates == 0 || attrs < 5) return {};

    const auto at = [&](size_t candidate, size_t attr) -> float {
        if (attrMajor) return safeValue(data[attr * candidates + candidate]);
        return safeValue(data[candidate * attrs + attr]);
    };

    std::vector<Candidate> candidatesOut;
    candidatesOut.reserve(std::min<size_t>(candidates, 4096));

    // 端到端导出：[1, N, 6+] = x1, y1, x2, y2, score, class_id, mask coefficients...
    // 分割模型后面的 mask coefficients 只用于掩膜，检测框解析不能把它们当作类别分数。
    const bool endToEndRows = !attrMajor
        && attrs >= 6
        && (config.outputLayout == YoloOutputLayout::EndToEnd
            || (config.outputLayout == YoloOutputLayout::Auto && attrs == 6));
    if (endToEndRows) {
        for (size_t i = 0; i < candidates; ++i) {
            const float score = at(i, 4);
            const int classId = static_cast<int>(std::round(at(i, 5)));
            if (score < config.confidence || classId < 0) continue;
            if (config.classFilterId >= 0 && classId != config.classFilterId) continue;

            const cv::Rect2f letterboxRect = xyxyToRect(
                at(i, 0), at(i, 1), at(i, 2), at(i, 3), meta);
            if (letterboxRect.width <= 1e-3f || letterboxRect.height <= 1e-3f) continue;
            const cv::Rect2f originalRect = mapBoxToOriginal(letterboxRect, meta);
            if (originalRect.width <= 1.0f || originalRect.height <= 1.0f) continue;
            candidatesOut.push_back({originalRect, score, classId});
        }
        return nms(candidatesOut, config);
    }
    if (config.outputLayout == YoloOutputLayout::EndToEnd) return {};

    const bool yoloV5LikeObjectness = (attrs == 85);
    const int classStart = yoloV5LikeObjectness ? 5 : 4;
    const int classCount = static_cast<int>(attrs) - classStart;
    if (classCount <= 0) return {};

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
