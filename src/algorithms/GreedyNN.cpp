// ============================================================================
//  GreedyNN.cpp
//  ----------------------------------------------------------------------------
//  Implementación del Vecino Más Cercano (mismo pseudocódigo del informe).
//
//  Idea:
//    - Empezamos en el depósito con la capacidad completa.
//    - En cada paso vamos al cliente NO visitado más cercano cuya demanda
//      todavía cabe en el vehículo.
//    - Si ninguno cabe, volvemos al depósito y arrancamos una ruta nueva.
//    - Terminamos cuando todos los clientes fueron visitados.
// ============================================================================
#include "GreedyNN.h"
#include <limits>
#include <set>

GreedyNN::GreedyNN() {}

std::string GreedyNN::nombre() const {
    return "Greedy (Vecino más cercano)";
}

Solucion GreedyNN::resolver(const Instancia& inst) {
    Solucion sol;

    const int n = inst.cantidadNodos();   // incluye al depósito
    const int Q = inst.capacidad();

    // Conjunto de clientes que aún no han sido visitados.
    // Los ids van desde 1 hasta n-1 (el 0 es el depósito).
    std::set<int> noVisitados;
    for (int i = 1; i < n; ++i) noVisitados.insert(i);

    // Mientras queden clientes sin visitar, construimos una ruta más.
    while (!noVisitados.empty()) {

        Ruta rutaActual;
        rutaActual.push_back(0);          // arranca en el depósito
        int capacidadRestante = Q;
        int nodoActual        = 0;

        // Vamos llenando la ruta hasta que ya no quepa nadie.
        while (true) {
            int    mejorVecino  = -1;
            double minDistancia = std::numeric_limits<double>::infinity();

            // Buscamos el cliente más cercano cuya demanda entre en la carga.
            for (int cliente : noVisitados) {
                int demanda = inst.nodo(cliente).demanda;
                if (demanda <= capacidadRestante) {
                    double d = inst.distancia(nodoActual, cliente);
                    if (d < minDistancia) {
                        minDistancia = d;
                        mejorVecino  = cliente;
                    }
                }
            }

            // Si no encontramos ningún candidato, cerramos la ruta.
            if (mejorVecino == -1) break;

            // Añadimos el cliente a la ruta.
            rutaActual.push_back(mejorVecino);
            capacidadRestante -= inst.nodo(mejorVecino).demanda;
            noVisitados.erase(mejorVecino);
            nodoActual = mejorVecino;
        }

        // Cerramos la ruta volviendo al depósito.
        rutaActual.push_back(0);
        sol.agregarRuta(rutaActual);
    }

    return sol;
}
