#pragma once

#include "../graph.hpp"
#include "../cost_matrix.hpp"
#include "../solution.hpp"
#include <vector>
#include <limits>
#include <algorithm>

namespace vrp {
namespace builders {

class NearestNeighbor {
private:
    const Graph& graph;
    const CostMatrix& costs;
    int depot;
    double vehicle_capacity;

public:
    NearestNeighbor(const Graph& g, const CostMatrix& c, int depot_id, double capacity)
        : graph(g), costs(c), depot(depot_id), vehicle_capacity(capacity) {}

    Solution solve() {
        int n = graph.size();
        std::vector<bool> visited(n, false);
        visited[depot] = true;  // Depot always "visited"

        Solution solution;
        int vehicle_id = 0;

        // Greedy: repeatedly build routes until all clients served
        while (true) {
            Route route;
            route.vehicle_id = vehicle_id;
            route.sequence.push_back(depot);

            int current = depot;
            double load = 0.0;
            bool added_any = false;

            // Inner loop: extend current route greedily
            for (int iter = 0; iter < n; ++iter) {
                int best_next = -1;
                double best_cost = std::numeric_limits<double>::infinity();

                // Find nearest unvisited client that fits capacity
                for (int j = 0; j < n; ++j) {
                    if (!visited[j]) {
                        const Node& client = graph.get_node(j);
                        double new_load = load + client.demand;

                        if (new_load <= vehicle_capacity) {
                            double edge_cost = costs.get_cost(current, j);
                            if (edge_cost < best_cost) {
                                best_cost = edge_cost;
                                best_next = j;
                            }
                        }
                    }
                }

                if (best_next == -1) {
                    // No more clients fit; close this route
                    break;
                }

                // Extend route
                visited[best_next] = true;
                const Node& client = graph.get_node(best_next);
                load += client.demand;
                route.sequence.push_back(best_next);
                route.cost += best_cost;
                current = best_next;
                added_any = true;
            }

            // Close route back to depot
            if (added_any) {
                route.cost += costs.get_cost(current, depot);
                route.sequence.push_back(depot);
                solution.routes.push_back(route);
                vehicle_id++;
            }

            // Check if all clients visited
            bool all_visited = true;
            for (int i = 0; i < n; ++i) {
                if (i != depot && !visited[i]) {
                    all_visited = false;
                    break;
                }
            }

            if (all_visited) break;
        }

        solution.calculate_total_cost();
        return solution;
    }
};

} // namespace builders
} // namespace vrp
