/*
 * bindings.cpp - pybind11 Python<→C++ interface
 *
 * Expone el C++ core al Python orchestrator vía zero-copy bindings.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "../include/graph.hpp"
#include "../include/cost_matrix.hpp"
#include "../include/solution.hpp"
#include "../include/builders/nearest_neighbor.hpp"
#include "../include/optimizers/simulated_annealing.hpp"
#include "../include/operators/local_search.hpp"

namespace py = pybind11;
using namespace vrp;
using namespace vrp::builders;
using namespace vrp::optimizers;
using namespace vrp::operators;

PYBIND11_MODULE(vrp_solver, m) {
    m.doc() = "VRP Solver - C++ core bindings";

    // Graph bindings
    py::class_<Coordinate>(m, "Coordinate")
        .def(py::init<>())
        .def_readwrite("x", &Coordinate::x)
        .def_readwrite("y", &Coordinate::y);

    py::class_<Node>(m, "Node")
        .def(py::init<>())
        .def_readwrite("id", &Node::id)
        .def_readwrite("demand", &Node::demand);

    py::class_<Graph>(m, "Graph")
        .def(py::init<int>())
        .def("add_node", &Graph::add_node)
        .def("size", &Graph::size);

    // CostMatrix bindings
    py::class_<CostMatrix>(m, "CostMatrix")
        .def(py::init<size_t>())
        .def("get_cost", &CostMatrix::get_cost)
        .def("set_cost", &CostMatrix::set_cost)
        .def("size", &CostMatrix::size)
        .def("is_valid", &CostMatrix::is_valid)
        .def_static("from_euclidean", &CostMatrix::from_euclidean);

    // Solution bindings
    py::class_<Route>(m, "Route")
        .def(py::init<>())
        .def_readwrite("vehicle_id", &Route::vehicle_id)
        .def_readwrite("sequence", &Route::sequence)
        .def_readwrite("cost", &Route::cost);

    py::class_<Solution>(m, "Solution")
        .def(py::init<>())
        .def_readwrite("routes", &Solution::routes)
        .def_readwrite("total_cost", &Solution::total_cost)
        .def("is_valid", &Solution::is_valid)
        .def("count_vehicles", &Solution::count_vehicles)
        .def("calculate_total_cost", &Solution::calculate_total_cost);

    // NearestNeighbor solver binding
    py::class_<NearestNeighbor>(m, "NearestNeighbor")
        .def(py::init<const Graph&, const CostMatrix&, int, double>())
        .def("solve", &NearestNeighbor::solve);

    // SimulatedAnnealing optimizer binding
    py::class_<SimulatedAnnealing>(m, "SimulatedAnnealing")
        .def(py::init<const Graph&, const CostMatrix&, double, double, int>(),
             py::arg("graph"),
             py::arg("cost_matrix"),
             py::arg("initial_temp") = 100.0,
             py::arg("cooling_rate") = 0.95,
             py::arg("iterations") = 1000)
        .def("solve", &SimulatedAnnealing::solve);

    // Local search operators binding
    py::class_<TwoOpt>(m, "TwoOpt")
        .def_static("improve", &TwoOpt::improve);

    py::class_<OrOpt>(m, "OrOpt")
        .def_static("improve", &OrOpt::improve);

    py::class_<ThreeOpt>(m, "ThreeOpt")
        .def_static("improve", &ThreeOpt::improve);
}
