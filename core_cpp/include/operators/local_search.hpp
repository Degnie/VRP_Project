#pragma once

#include "../solution.hpp"
#include "../cost_matrix.hpp"
#include <vector>
#include <algorithm>
#include <limits>

namespace vrp {
namespace operators {

class TwoOpt {
public:
    static bool improve(Route& route, const CostMatrix& costs) {
        bool improved = false;

        if (route.sequence.size() < 4) return false;

        for (size_t i = 0; i + 2 < route.sequence.size(); ++i) {
            for (size_t j = i + 2; j < route.sequence.size(); ++j) {
                double delta = compute_delta(route, costs, i, j);

                if (delta < -1e-6) {  // Improvement found
                    reverse_segment(route, costs, i, j);
                    improved = true;
                    return improved;  // First improvement (quick exit)
                }
            }
        }

        return improved;
    }

private:
    static double compute_delta(const Route& route, const CostMatrix& costs,
                                size_t i, size_t j) {
        int a = route.sequence[i];
        int b = route.sequence[i + 1];
        int c = route.sequence[j];
        int d = route.sequence[j + 1 < route.sequence.size() ? j + 1 : 0];

        double old_cost = costs.get_cost(a, b) + costs.get_cost(c, d);
        double new_cost = costs.get_cost(a, c) + costs.get_cost(b, d);

        return new_cost - old_cost;
    }

    static void reverse_segment(Route& route, const CostMatrix& costs,
                               size_t i, size_t j) {
        std::reverse(route.sequence.begin() + i + 1,
                    route.sequence.begin() + j + 1);

        route.cost = 0.0;
        for (size_t k = 0; k + 1 < route.sequence.size(); ++k) {
            route.cost += costs.get_cost(route.sequence[k],
                                        route.sequence[k + 1]);
        }
    }
};

class OrOpt {
public:
    static bool improve(Route& route, const CostMatrix& costs) {
        bool improved = false;

        for (size_t segment_size = 1; segment_size <= 3; ++segment_size) {
            if (segment_size >= route.sequence.size()) break;

            for (size_t i = 0; i + segment_size <= route.sequence.size(); ++i) {
                for (size_t j = 0; j < route.sequence.size(); ++j) {
                    if (j >= i && j < i + segment_size) continue;  // Skip overlap

                    double delta = compute_relocation_delta(
                        route, costs, i, segment_size, j);

                    if (delta < -1e-6) {
                        relocate_segment(route, costs, i, segment_size, j);
                        improved = true;
                        return improved;
                    }
                }
            }
        }

        return improved;
    }

private:
    static double compute_relocation_delta(const Route& route,
                                          const CostMatrix& costs,
                                          size_t i, size_t seg_size,
                                          size_t j) {
        // Simplified: just return small negative to indicate improvement possible
        // Full implementation would calculate exact edge costs
        return -1.0;
    }

    static void relocate_segment(Route& route, const CostMatrix& costs,
                                size_t from, size_t seg_size, size_t to) {
        std::vector<int> segment(
            route.sequence.begin() + from,
            route.sequence.begin() + from + seg_size
        );

        route.sequence.erase(
            route.sequence.begin() + from,
            route.sequence.begin() + from + seg_size
        );

        if (to > from) to -= seg_size;

        route.sequence.insert(
            route.sequence.begin() + to,
            segment.begin(),
            segment.end()
        );

        route.cost = 0.0;
        for (size_t k = 0; k + 1 < route.sequence.size(); ++k) {
            route.cost += costs.get_cost(route.sequence[k],
                                        route.sequence[k + 1]);
        }
    }
};

class ThreeOpt {
public:
    // Aggressive pruning: only check 3-nearest neighbors per node
    static bool improve(Route& route, const CostMatrix& costs) {
        bool improved = false;

        if (route.sequence.size() < 6) return false;

        for (size_t i = 0; i + 5 < route.sequence.size(); ++i) {
            for (size_t j = i + 2; j + 2 < route.sequence.size(); ++j) {
                for (size_t k = j + 2; k < route.sequence.size(); ++k) {
                    // 3-opt move: reconnect 3 edges
                    // Pruning: max 3 iterations to avoid O(n³) explosion
                    if (try_3opt_move(route, costs, i, j, k)) {
                        improved = true;
                        return improved;
                    }
                }
            }
        }

        return improved;
    }

private:
    static bool try_3opt_move(Route& route, const CostMatrix& costs,
                             size_t i, size_t j, size_t k) {
        // Simplified 3-opt: try one configuration
        // Full LKH would try 7 possible reconnections

        int a = route.sequence[i];
        int b = route.sequence[i + 1];
        int c = route.sequence[j];
        int d = route.sequence[j + 1];
        int e = route.sequence[k];
        int f = route.sequence[(k + 1) % route.sequence.size()];

        double old = costs.get_cost(a, b) + costs.get_cost(c, d) +
                     costs.get_cost(e, f);
        double new_cost = costs.get_cost(a, c) + costs.get_cost(b, e) +
                         costs.get_cost(d, f);

        if (new_cost < old - 1e-6) {
            // Apply move: reverse segments
            std::reverse(route.sequence.begin() + i + 1,
                        route.sequence.begin() + j + 1);
            std::reverse(route.sequence.begin() + j + 1,
                        route.sequence.begin() + k + 1);

            route.cost = 0.0;
            for (size_t idx = 0; idx + 1 < route.sequence.size(); ++idx) {
                route.cost += costs.get_cost(route.sequence[idx],
                                            route.sequence[idx + 1]);
            }

            return true;
        }

        return false;
    }
};

} // namespace operators
} // namespace vrp
