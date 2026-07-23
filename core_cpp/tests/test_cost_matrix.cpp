#include <gtest/gtest.h>
#include "cost_matrix.hpp"
#include <cmath>

using namespace vrp;

TEST(CostMatrixTest, GetSet) {
    CostMatrix m(3);
    m.set_cost(0, 1, 5.0);
    EXPECT_DOUBLE_EQ(m.get_cost(0, 1), 5.0);
}

TEST(CostMatrixTest, Asymmetric) {
    CostMatrix m(3);
    m.set_cost(0, 1, 5.0);
    m.set_cost(1, 0, 7.0);  // Different!
    EXPECT_NE(m.get_cost(0, 1), m.get_cost(1, 0));
}

TEST(CostMatrixTest, FromEuclidean) {
    std::vector<std::pair<double, double>> coords = {
        {0.0, 0.0},
        {3.0, 4.0},
    };
    auto m = CostMatrix::from_euclidean(coords);
    EXPECT_DOUBLE_EQ(m.get_cost(0, 1), 5.0);
}

TEST(CostMatrixTest, NegativeCostNotAllowed) {
    CostMatrix m(3);
    EXPECT_THROW(m.set_cost(0, 1, -1.0), std::invalid_argument);
}
