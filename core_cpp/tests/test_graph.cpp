#include <gtest/gtest.h>
#include "graph.hpp"

using namespace vrp;

TEST(GraphTest, AddNode) {
    Graph g(5);
    g.add_node(0, 0.0, 0.0, 0);  // depot
    g.add_node(1, 1.0, 1.0, 10);
    
    const auto& node = g.get_node(1);
    EXPECT_EQ(node.id, 1);
    EXPECT_EQ(node.demand, 10);
}

TEST(GraphTest, EuclideanDistance) {
    Coordinate a{0.0, 0.0};
    Coordinate b{3.0, 4.0};
    double dist = Graph::euclidean_distance(a, b);
    EXPECT_DOUBLE_EQ(dist, 5.0);
}

TEST(GraphTest, InvalidDemand) {
    Graph g(5);
    EXPECT_THROW(g.add_node(0, 0.0, 0.0, -1), std::invalid_argument);
}
