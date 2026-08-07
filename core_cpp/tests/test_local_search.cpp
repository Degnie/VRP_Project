#include <gtest/gtest.h>
#include "graph.hpp"
#include "cost_matrix.hpp"
#include "solution.hpp"
#include "operators/local_search.hpp"

using namespace vrp;
using namespace vrp::operators;

namespace {

// Depósito en (0,0). Cluster A cerca de (1,0)-(3,0), cliente aislado en
// (100,0) — muy lejos, pero la ruta 1 (con espacio) lo visita primero por
// construcción NN "atascada", dejando la ruta 0 corta pese a tener espacio
// para más clientes cercanos. RelocateInterRoute debe mover el cliente
// aislado y disminuir el costo total solo si hay una ruta con capacidad
// real que lo reciba a menor costo neto.
CostMatrix build_costs(int n_nodes, const std::vector<Coordinate>& coords) {
    std::vector<std::pair<double, double>> pairs;
    for (const auto& c : coords) pairs.emplace_back(c.x, c.y);
    return CostMatrix::from_euclidean(pairs);
}

}  // namespace

TEST(RelocateInterRouteTest, MovesIsolatedClientToCloserRouteWithCapacity) {
    // Nodos: 0=depot, 1=cliente aislado (lejos, ruta 0), 2,3=cluster cercano (ruta 1)
    Graph graph(4);
    graph.add_node(0, 0.0, 0.0, 0);
    graph.add_node(1, 100.0, 0.0, 5);
    graph.add_node(2, 1.0, 0.0, 5);
    graph.add_node(3, 2.0, 0.0, 5);

    std::vector<Coordinate> coords = {{0, 0}, {100, 0}, {1, 0}, {2, 0}};
    CostMatrix costs = build_costs(4, coords);

    Solution sol;
    // Ruta 0: depot -> 1 (aislado) -> depot. Capacidad sobrante: 10 (cap 15, usa 5).
    Route r0;
    r0.vehicle_id = 0;
    r0.sequence = {0, 1, 0};
    r0.cost = costs.get_cost(0, 1) + costs.get_cost(1, 0);
    sol.routes.push_back(r0);

    // Ruta 1: depot -> 2 -> 3 -> depot. Capacidad sobrante: 0 (cap 10, usa 10)
    // -- sin espacio para recibir al cliente 1 (demand 5).
    Route r1;
    r1.vehicle_id = 1;
    r1.sequence = {0, 2, 3, 0};
    r1.cost = costs.get_cost(0, 2) + costs.get_cost(2, 3) + costs.get_cost(3, 0);
    sol.routes.push_back(r1);

    std::vector<double> capacities = {15.0, 15.0};  // ambas con espacio si r1 recibe al cliente 1

    double cost_before = sol.calculate_total_cost();
    bool improved = RelocateInterRoute::improve(sol, graph, costs, capacities);
    sol.calculate_total_cost();

    ASSERT_TRUE(improved);
    EXPECT_LT(sol.total_cost, cost_before);

    // El cliente 1 debe haber quedado en la MISMA ruta donde estaban 2 y 3
    // (o al menos, la ruta 0 debe haber quedado sin el cliente 1 aislado).
    bool ruta0_tiene_cliente1 = false;
    for (auto& route : sol.routes) {
        if (route.vehicle_id == 0) {
            for (int node : route.sequence) {
                if (node == 1) ruta0_tiene_cliente1 = true;
            }
        }
    }
    EXPECT_FALSE(ruta0_tiene_cliente1);
}

TEST(RelocateInterRouteTest, RespectsCapacityDoesNotOverload) {
    // Mismo escenario, pero SIN espacio en la ruta 1 (capacidad justa) --
    // no debe mover nada que rompa la restricción de capacidad.
    Graph graph(4);
    graph.add_node(0, 0.0, 0.0, 0);
    graph.add_node(1, 100.0, 0.0, 5);
    graph.add_node(2, 1.0, 0.0, 5);
    graph.add_node(3, 2.0, 0.0, 5);

    std::vector<Coordinate> coords = {{0, 0}, {100, 0}, {1, 0}, {2, 0}};
    CostMatrix costs = build_costs(4, coords);

    Solution sol;
    Route r0;
    r0.vehicle_id = 0;
    r0.sequence = {0, 1, 0};
    r0.cost = costs.get_cost(0, 1) + costs.get_cost(1, 0);
    sol.routes.push_back(r0);

    Route r1;
    r1.vehicle_id = 1;
    r1.sequence = {0, 2, 3, 0};
    r1.cost = costs.get_cost(0, 2) + costs.get_cost(2, 3) + costs.get_cost(3, 0);
    sol.routes.push_back(r1);

    std::vector<double> capacities = {15.0, 10.0};  // r1 exactamente llena (10), sin espacio para +5

    RelocateInterRoute::improve(sol, graph, costs, capacities);

    for (auto& route : sol.routes) {
        int load = 0;
        for (int node : route.sequence) {
            load += graph.get_node(node).demand;
        }
        double cap = capacities[route.vehicle_id % capacities.size()];
        EXPECT_LE(load, cap);
    }
}

TEST(RelocateInterRouteTest, NoImprovementWhenAlreadyOptimal) {
    // Cluster único, todos cerca entre sí, ya en la ruta más barata posible
    // -- no debe reportar mejora ni cambiar nada.
    Graph graph(3);
    graph.add_node(0, 0.0, 0.0, 0);
    graph.add_node(1, 1.0, 0.0, 5);
    graph.add_node(2, 2.0, 0.0, 5);

    std::vector<Coordinate> coords = {{0, 0}, {1, 0}, {2, 0}};
    CostMatrix costs = build_costs(3, coords);

    Solution sol;
    Route r0;
    r0.vehicle_id = 0;
    r0.sequence = {0, 1, 2, 0};
    r0.cost = costs.get_cost(0, 1) + costs.get_cost(1, 2) + costs.get_cost(2, 0);
    sol.routes.push_back(r0);

    std::vector<double> capacities = {10.0};

    bool improved = RelocateInterRoute::improve(sol, graph, costs, capacities);
    EXPECT_FALSE(improved);
}
