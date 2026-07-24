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

# Tests — EXCLUDE_FROM_ALL evita que "cmake --build ." (target ALL) compile
# gtest/gmock y el ejecutable de tests en un build normal; solo se compilan
# con "ctest" o "cmake --build . --target vrp_core_tests" explícitos.
if(BUILD_TESTS)
    add_subdirectory(tests EXCLUDE_FROM_ALL)
endif()
