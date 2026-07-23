#include <gtest/gtest.h>
#include "solution.hpp"

using namespace vrp;

TEST(SolutionTest, CountVehicles) {
    Solution sol;
    sol.routes.push_back({0, {0, 1, 2, 0}, 10.0});
    sol.routes.push_back({1, {0, 3, 4, 0}, 12.0});
    EXPECT_EQ(sol.count_vehicles(), 2);
}

TEST(SolutionTest, CalculateTotalCost) {
    Solution sol;
    sol.routes.push_back({0, {0, 1, 2, 0}, 10.0});
    sol.routes.push_back({1, {0, 3, 4, 0}, 12.0});
    double total = sol.calculate_total_cost();
    EXPECT_DOUBLE_EQ(total, 22.0);
}
