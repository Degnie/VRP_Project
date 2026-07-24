/*
 * graph.hpp - Estructura de grafo dirigido
 *
 * Representa la red de clientes y depósito.
 * Soporta aristas dirigidas (asimétricas).
 */

#pragma once

#include <vector>
#include <stdexcept>
#include <cmath>

namespace vrp {

struct Coordinate {
    double x, y;
};

struct Node {
    int id;
    Coordinate location;
    int demand = 0;  // 0 para depósito
};

class Graph {
private:
    int n_nodes;
    std::vector<Node> nodes;
    std::vector<bool> assigned;

public:
    explicit Graph(int n) : n_nodes(n), nodes(n), assigned(n, false) {}

    void add_node(int id, double x, double y, int demand = 0) {
        if (id < 0 || id >= n_nodes) {
            throw std::out_of_range("Node ID out of bounds");
        }
        if (demand < 0) {
            throw std::invalid_argument("Demand must be non-negative");
        }
        if (assigned[id]) {
            throw std::invalid_argument("Node ID already assigned (duplicate add_node call)");
        }
        nodes[id] = {id, {x, y}, demand};
        assigned[id] = true;
    }

    const Node& get_node(int id) const {
        if (id < 0 || id >= n_nodes) {
            throw std::out_of_range("Node ID out of bounds");
        }
        return nodes[id];
    }

    int size() const { return n_nodes; }

    // Euclidean distance (helper; actual distances come from CostMatrix)
    static double euclidean_distance(const Coordinate& a, const Coordinate& b) {
        double dx = b.x - a.x;
        double dy = b.y - a.y;
        return std::sqrt(dx * dx + dy * dy);
    }
};

}  // namespace vrp
