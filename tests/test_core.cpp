// ============================================================================
//  test_core.cpp
//  ----------------------------------------------------------------------------
//  Prueba de humo del NÚCLEO del proyecto sin depender de Qt.
//  Sirve para verificar que Greedy y SA producen soluciones válidas
//  antes de instalar Qt en la máquina.
//
//  Compilación (desde la carpeta raíz del proyecto):
//      g++ -std=c++17 -O2 -Isrc tests/test_core.cpp
//          src/core/Instancia.cpp src/core/Solucion.cpp
//          src/algorithms/GreedyNN.cpp src/algorithms/SimulatedAnnealing.cpp
//          src/io/LectorInstancia.cpp
//          -o test_core
//
//  Ejecución:
//    ./test_core
// ============================================================================
#include "../src/core/Instancia.h"
#include "../src/core/Solucion.h"
#include "../src/algorithms/GreedyNN.h"
#include "../src/algorithms/SimulatedAnnealing.h"
#include "../src/io/LectorInstancia.h"

#include <chrono>
#include <iostream>

int main() {
    Instancia inst;
    std::string err;
    if (!LectorInstancia::cargar("data/ejemplo_10.vrp", inst, err)) {
        std::cerr << "Error: " << err << "\n";
        return 1;
    }
    std::cout << "Instancia: " << inst.nombre()
              << "  n=" << inst.cantidadClientes()
              << "  Q=" << inst.capacidad() << "\n\n";

    using namespace std::chrono;

    // Greedy
    GreedyNN g;
    auto t0 = high_resolution_clock::now();
    Solucion sg = g.resolver(inst);
    auto t1 = high_resolution_clock::now();
    double msG = duration<double, std::milli>(t1 - t0).count();

    std::cout << "GREEDY  costo=" << sg.costoTotal(inst)
              << "  rutas=" << sg.cantidadRutas()
              << "  valida=" << (sg.esValida(inst) ? "SI" : "NO")
              << "  tiempo=" << msG << " ms\n";
    for (int i = 0; i < sg.cantidadRutas(); ++i) {
        std::cout << "  R" << i << ":";
        for (int id : sg.ruta(i)) std::cout << " " << id;
        std::cout << "\n";
    }

    // SA
    SimulatedAnnealing sa;
    auto t2 = high_resolution_clock::now();
    Solucion ssa = sa.resolver(inst);
    auto t3 = high_resolution_clock::now();
    double msSA = duration<double, std::milli>(t3 - t2).count();

    std::cout << "\nSA      costo=" << ssa.costoTotal(inst)
              << "  rutas=" << ssa.cantidadRutas()
              << "  valida=" << (ssa.esValida(inst) ? "SI" : "NO")
              << "  tiempo=" << msSA << " ms\n";
    for (int i = 0; i < ssa.cantidadRutas(); ++i) {
        std::cout << "  R" << i << ":";
        for (int id : ssa.ruta(i)) std::cout << " " << id;
        std::cout << "\n";
    }

    double mejora = (sg.costoTotal(inst) - ssa.costoTotal(inst)) / sg.costoTotal(inst) * 100.0;
    std::cout << "\nMejora SA vs Greedy: " << mejora << " %\n";
    return 0;
}
