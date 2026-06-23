#pragma once

#include <vector>

struct MatchPair {
    int track = -1;
    int detection = -1;
};

std::vector<MatchPair> greedyMatch(const std::vector<std::vector<float>>& scores, float minScore);
