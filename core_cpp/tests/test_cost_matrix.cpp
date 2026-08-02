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

TEST(CostMatrixTest, SetCostsBulkMatchesCellByCell) {
    CostMatrix bulk(3);
    CostMatrix cell(3);

    std::vector<double> flat = {
        0.0, 1.0, 2.0,
        3.0, 0.0, 4.0,
        5.0, 6.0, 0.0,
    };
    bulk.set_costs_bulk(flat.data(), flat.size());

    for (size_t i = 0; i < 3; ++i) {
        for (size_t j = 0; j < 3; ++j) {
            cell.set_cost(i, j, flat[i * 3 + j]);
        }
    }

    for (size_t i = 0; i < 3; ++i) {
        for (size_t j = 0; j < 3; ++j) {
            EXPECT_DOUBLE_EQ(bulk.get_cost(i, j), cell.get_cost(i, j));
        }
    }
}

TEST(CostMatrixTest, SetCostsBulkRejectsWrongSize) {
    CostMatrix m(3);
    std::vector<double> flat = {0.0, 1.0, 2.0};  // 3, not 3*3=9
    EXPECT_THROW(m.set_costs_bulk(flat.data(), flat.size()), std::invalid_argument);
}

TEST(CostMatrixTest, SetCostsBulkRejectsNegative) {
    CostMatrix m(2);
    std::vector<double> flat = {0.0, -1.0, 1.0, 0.0};
    EXPECT_THROW(m.set_costs_bulk(flat.data(), flat.size()), std::invalid_argument);
}
