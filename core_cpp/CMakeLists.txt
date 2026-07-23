# CMakeLists.txt for core_cpp

# Core library
add_library(vrp_core
    src/graph.cpp
    src/cost_matrix.cpp
    src/solution.cpp
)

target_include_directories(vrp_core PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# C++17 features
target_compile_features(vrp_core PRIVATE cxx_std_17)

# Optimization flags
if(MSVC)
    target_compile_options(vrp_core PRIVATE /O2 /Wall)
else()
    target_compile_options(vrp_core PRIVATE -O3 -Wall -Wextra -pedantic)
endif()

# Tests
if(BUILD_TESTS)
    add_subdirectory(tests)
endif()
