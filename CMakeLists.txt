# =============================================================================
#  CMakeLists.txt — Proyecto VRP (Greedy + Simulated Annealing) con Qt
#  ---------------------------------------------------------------------------
#  Cómo compilar:
#
#     mkdir build
#     cd build
#     cmake ..
#     cmake --build .
#
#  Requisitos:
#     - CMake 3.16 o superior
#     - Compilador con soporte C++17 (g++, clang, MSVC)
#     - Qt 6 (recomendado) o Qt 5 (también funciona)
# =============================================================================
cmake_minimum_required(VERSION 3.16)

project(VRP_Solver LANGUAGES CXX)

# ---- Configuración general ----
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Sin tipo de build explícito, compilamos optimizado (esto es lo que la
# metaheurística necesita para correr rápido en instancias grandes).
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release)
endif()

if(MSVC)
    set(CMAKE_CXX_FLAGS_RELEASE "/O2 /DNDEBUG")
else()
    set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")
endif()

# Qt necesita generar código extra (MOC) para las clases con Q_OBJECT.
# Estas tres líneas hacen que CMake lo haga automáticamente.
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTORCC ON)

# ---- Búsqueda de Qt (intenta Qt6 primero, luego Qt5) ----
# Concurrent: para correr los solvers fuera del hilo de la UI (QtConcurrent::run).
find_package(Qt6 QUIET COMPONENTS Widgets Concurrent)
if (NOT Qt6_FOUND)
    find_package(Qt5 REQUIRED COMPONENTS Widgets Concurrent)
    set(QT_LIBS Qt5::Widgets Qt5::Concurrent)
    message(STATUS "Usando Qt5")
else()
    set(QT_LIBS Qt6::Widgets Qt6::Concurrent)
    message(STATUS "Usando Qt6")
endif()

# ---- Lista de archivos fuente ----
set(FUENTES
    src/main.cpp

    src/core/Instancia.cpp
    src/core/Solucion.cpp

    src/algorithms/GreedyNN.cpp
    src/algorithms/SimulatedAnnealing.cpp

    src/io/LectorInstancia.cpp

    src/gui/MainWindow.cpp
    src/gui/RouteView.cpp
)

set(CABECERAS
    src/core/Cliente.h
    src/core/Instancia.h
    src/core/Solucion.h

    src/algorithms/IVRPSolver.h
    src/algorithms/GreedyNN.h
    src/algorithms/SimulatedAnnealing.h

    src/io/LectorInstancia.h

    src/gui/MainWindow.h
    src/gui/RouteView.h
)

# ---- Creación del ejecutable ----
add_executable(VRP_Solver ${FUENTES} ${CABECERAS})

target_link_libraries(VRP_Solver PRIVATE ${QT_LIBS})

# Directorios de include (para que #include "..." encuentre los headers).
target_include_directories(VRP_Solver PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

# ---- Tests (test_core, sin Qt) ----
enable_testing()

add_executable(test_core
    tests/test_core.cpp
    src/core/Instancia.cpp
    src/core/Solucion.cpp
    src/algorithms/GreedyNN.cpp
    src/algorithms/SimulatedAnnealing.cpp
    src/io/LectorInstancia.cpp
)
target_include_directories(test_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)

add_test(NAME test_core
         COMMAND test_core ${CMAKE_CURRENT_SOURCE_DIR}/data/ejemplo_10.vrp)
