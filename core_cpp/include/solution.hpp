/*
 * solution.hpp - Estructura de solución
 *
 * Representa un conjunto de rutas que resuelven una instancia VRP.
 */

#pragma once

#include <vector>
#include <cmath>

namespace vrp {

struct Route {
    int vehicle_id;
    std::vector<int> sequence;  // Clients in order (including depot at start/end)
    double cost = 0.0;
};

struct Solution {
    std::vector<Route> routes;
    double total_cost = 0.0;

    bool is_valid() const {
        // TODO: implement validation
        return true;
    }

    int count_vehicles() const {
        return static_cast<int>(routes.size());
    }

    double calculate_total_cost() {
        total_cost = 0.0;
        for (const auto& route : routes) {
            total_cost += route.cost;
        }
        return total_cost;
    }
};

}  // namespace vrp
