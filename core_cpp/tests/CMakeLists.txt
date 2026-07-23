# C++ Tests

include(FetchContent)
FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/v1.14.0.zip
)

FetchContent_MakeAvailable(googletest)

# Test executable
add_executable(vrp_core_tests
    test_graph.cpp
    test_cost_matrix.cpp
    test_solution.cpp
)

target_link_libraries(vrp_core_tests
    vrp_core
    gtest
    gtest_main
)

target_include_directories(vrp_core_tests PRIVATE
    ${CMAKE_SOURCE_DIR}/core_cpp/include
)

add_test(
    NAME VRPCoreTests
    COMMAND vrp_core_tests
)
