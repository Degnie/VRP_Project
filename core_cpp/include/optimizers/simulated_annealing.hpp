#pragma once

#include "../graph.hpp"
#include "../cost_matrix.hpp"
#include "../solution.hpp"
#include <vector>
#include <random>
#include <cmath>
#include <limits>

namespace vrp {
namespace optimizers {

class SimulatedAnnealing {
private:
    const Graph& graph;
    const CostMatrix& costs;
    std::mt19937 rng;

    // Parameters
    double T0;
    double alpha;
    int max_iterations;

public:
    SimulatedAnnealing(
        const Graph& g,
        const CostMatrix& c,
        double initial_temp = 100.0,
        double cooling_rate = 0.95,
        int iterations = 1000
    )
        : graph(g), costs(c), T0(initial_temp), alpha(cooling_rate),
          max_iterations(iterations), rng(std::random_device{}()) {}

    Solution solve(const Solution& initial_solution) {
        Solution best = initial_solution;
        Solution current = initial_solution;
        double best_cost = current.calculate_total_cost();
        double current_cost = best_cost;

        std::uniform_real_distribution<double> rand_uniform(0.0, 1.0);

        for (int iteration = 0; iteration < max_iterations; ++iteration) {
            double temperature = T0 * std::pow(alpha, iteration);

            if (temperature < 1e-6) break;  // Converged

            // Try 2-opt move
            Solution candidate = two_opt_move(current);
            double candidate_cost = candidate.calculate_total_cost();
            double delta = candidate_cost - current_cost;

            // Metropolis criterion
            if (delta < 0 || rand_uniform(rng) < std::exp(-delta / temperature)) {
                current = candidate;
                current_cost = candidate_cost;

                if (current_cost < best_cost) {
                    best = current;
                    best_cost = current_cost;
                }
            }
        }

        return best;
    }

private:
    Solution two_opt_move(const Solution& sol) {
        if (sol.routes.empty()) return sol;

        Solution result = sol;
        auto& routes = result.routes;

        // Pick random route
        std::uniform_int_distribution<size_t> route_dist(0, routes.size() - 1);
        size_t route_idx = route_dist(rng);
        auto& route = routes[route_idx];

        if (route.sequence.size() < 4) return result;  // Need at least 4 nodes

        // Pick two random positions in route
        std::uniform_int_distribution<size_t> pos_dist(1, route.sequence.size() - 2);
        size_t i = pos_dist(rng);
        size_t j = pos_dist(rng);

        if (i > j) std::swap(i, j);
        if (i == j || i + 1 == j) return result;  // No change

        // Reverse segment [i..j]
        std::reverse(route.sequence.begin() + i, route.sequence.begin() + j + 1);

        // Recalculate cost
        route.cost = calculate_route_cost(route);

        return result;
    }

    double calculate_route_cost(const Route& route) {
        double cost = 0.0;
        for (size_t i = 0; i + 1 < route.sequence.size(); ++i) {
            cost += costs.get_cost(route.sequence[i], route.sequence[i + 1]);
        }
        return cost;
    }
};

} // namespace optimizers
} // namespace vrp
