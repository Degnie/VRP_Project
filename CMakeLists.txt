cmake_minimum_required(VERSION 3.20)
project(VRPSolver CXX)

# C++17 standard (C++20 not available in all environments)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build options
option(BUILD_TESTS "Build C++ tests" ON)
option(BUILD_PYTHON_BINDINGS "Build Python bindings" ON)

# Add core_cpp directory
add_subdirectory(core_cpp)

# Python bindings (if enabled)
if(BUILD_PYTHON_BINDINGS)
    find_package(Python3 COMPONENTS Interpreter Development)
    find_package(pybind11 CONFIG)

    if(Python3_FOUND AND pybind11_FOUND)
        pybind11_add_module(vrp_solver
            core_cpp/src/bindings.cpp
        )

        target_include_directories(vrp_solver PRIVATE
            ${CMAKE_SOURCE_DIR}/core_cpp/include
        )

        target_link_libraries(vrp_solver PRIVATE
            vrp_core
        )
        message(STATUS "Python bindings: ENABLED")
    else()
        message(STATUS "Python bindings: DISABLED (Python3 or pybind11 not found)")
    endif()
endif()

# Testing (if enabled)
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(core_cpp/tests EXCLUDE_FROM_ALL)
endif()

# Print configuration
message(STATUS "VRP Solver Configuration:")
message(STATUS "  C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "  Python Bindings: ${BUILD_PYTHON_BINDINGS}")
message(STATUS "  Tests: ${BUILD_TESTS}")
