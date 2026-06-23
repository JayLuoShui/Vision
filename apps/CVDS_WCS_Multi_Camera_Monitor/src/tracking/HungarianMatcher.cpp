#include "tracking/HungarianMatcher.h"

#include <algorithm>

std::vector<MatchPair> greedyMatch(const std::vector<std::vector<float>>& scores, float minScore) {
    std::vector<MatchPair> matches;
    if (scores.empty()) return matches;
    std::vector<bool> usedRows(scores.size(), false);
    std::vector<bool> usedCols(scores.front().size(), false);
    while (true) {
        int bestRow = -1;
        int bestCol = -1;
        float best = minScore;
        for (size_t r = 0; r < scores.size(); ++r) {
            if (usedRows[r]) continue;
            for (size_t c = 0; c < scores[r].size(); ++c) {
                if (!usedCols[c] && scores[r][c] > best) {
                    best = scores[r][c];
                    bestRow = static_cast<int>(r);
                    bestCol = static_cast<int>(c);
                }
            }
        }
        if (bestRow < 0) break;
        usedRows[bestRow] = true;
        usedCols[bestCol] = true;
        matches.push_back({bestRow, bestCol});
    }
    return matches;
}
