/*
 * cost_matrix.hpp - Matriz de costo dirigida (asimétrica)
 *
 * Inspirado en Vroom: no asume simetría euclidiana.
 * Permite distancias reales, one-way streets, peajes, etc.
 */

#pragma once

#include <vector>
#include <cmath>
#include <stdexcept>
#include <limits>

namespace vrp {

class CostMatrix {
private:
    size_t n_nodes;
    std::vector<std::vector<double>> costs;

public:
    explicit CostMatrix(size_t n)
        : n_nodes(n), costs(n, std::vector<double>(n, 0.0)) {}

    // Get cost from→to (may differ from to→from)
    double get_cost(int from, int to) const {
        validate_indices(from, to);
        return costs[from][to];
    }

    void set_cost(int from, int to, double cost) {
        validate_indices(from, to);
        if (cost < 0 && cost != std::numeric_limits<double>::infinity()) {
            throw std::invalid_argument("Negative costs not allowed");
        }
        costs[from][to] = cost;
    }

    size_t size() const { return n_nodes; }

    bool is_valid() const {
        for (const auto& row : costs) {
            for (double cost : row) {
                if (cost < 0 && cost != std::numeric_limits<double>::infinity()) {
                    return false;
                }
            }
        }
        return true;
    }

    // Builder: construct from Euclidean coordinates (symmetric case)
    static CostMatrix from_euclidean(
        const std::vector<std::pair<double, double>>& coords
    ) {
        size_t n = coords.size();
        CostMatrix m(n);

        for (size_t i = 0; i < n; ++i) {
            for (size_t j = 0; j < n; ++j) {
                if (i == j) {
                    m.set_cost(i, j, 0.0);
                } else {
                    double dx = coords[j].first - coords[i].first;
                    double dy = coords[j].second - coords[i].second;
                    double dist = std::sqrt(dx * dx + dy * dy);
                    m.set_cost(i, j, dist);
                }
            }
        }

        return m;
    }

private:
    void validate_indices(int from, int to) const {
        if (from < 0 || from >= static_cast<int>(n_nodes) ||
            to < 0 || to >= static_cast<int>(n_nodes)) {
            throw std::out_of_range("Cost matrix index out of bounds");
        }
    }
};

}  // namespace vrp
