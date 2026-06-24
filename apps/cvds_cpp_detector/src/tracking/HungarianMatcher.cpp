#include "tracking/HungarianMatcher.h"

#include <algorithm>
#include <cmath>
#include <limits>

std::vector<MatchPair> hungarianMatch(
    const std::vector<std::vector<float>>& scores,
    float minScore) {
    std::vector<MatchPair> matches;
    if (scores.empty()) return matches;
    const size_t columns = scores.front().size();
    if (columns == 0) return matches;
    for (const auto& row : scores) {
        if (row.size() != columns) return {};
    }

    const size_t originalRows = scores.size();
    const size_t originalColumns = columns;
    const size_t size = std::max(originalRows, originalColumns);
    const double invalidCost = 1e6;
    std::vector<std::vector<double>> cost(size + 1, std::vector<double>(size + 1, 1.0));
    for (size_t row = 0; row < originalRows; ++row) {
        for (size_t column = 0; column < originalColumns; ++column) {
            const float score = scores[row][column];
            cost[row + 1][column + 1] =
                std::isfinite(score) && score >= minScore ? 1.0 - score : invalidCost;
        }
    }

    std::vector<double> u(size + 1, 0.0);
    std::vector<double> v(size + 1, 0.0);
    std::vector<size_t> p(size + 1, 0);
    std::vector<size_t> way(size + 1, 0);
    for (size_t row = 1; row <= size; ++row) {
        p[0] = row;
        size_t column0 = 0;
        std::vector<double> minValue(size + 1, std::numeric_limits<double>::infinity());
        std::vector<bool> used(size + 1, false);
        do {
            used[column0] = true;
            const size_t row0 = p[column0];
            double delta = std::numeric_limits<double>::infinity();
            size_t column1 = 0;
            for (size_t column = 1; column <= size; ++column) {
                if (used[column]) continue;
                const double current = cost[row0][column] - u[row0] - v[column];
                if (current < minValue[column]) {
                    minValue[column] = current;
                    way[column] = column0;
                }
                if (minValue[column] < delta) {
                    delta = minValue[column];
                    column1 = column;
                }
            }
            for (size_t column = 0; column <= size; ++column) {
                if (used[column]) {
                    u[p[column]] += delta;
                    v[column] -= delta;
                } else {
                    minValue[column] -= delta;
                }
            }
            column0 = column1;
        } while (p[column0] != 0);

        do {
            const size_t column1 = way[column0];
            p[column0] = p[column1];
            column0 = column1;
        } while (column0 != 0);
    }

    for (size_t column = 1; column <= size; ++column) {
        const size_t row = p[column];
        if (row == 0 || row > originalRows || column > originalColumns) continue;
        const float score = scores[row - 1][column - 1];
        if (std::isfinite(score) && score >= minScore) {
            matches.push_back({
                static_cast<int>(row - 1),
                static_cast<int>(column - 1)});
        }
    }
    return matches;
}
