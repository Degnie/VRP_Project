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
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <vector>

GreedyNN::GreedyNN() {}

std::string GreedyNN::nombre() const {
    return "Greedy (Vecino más cercano)";
}

Solucion GreedyNN::resolver(const Instancia& inst) {
    Solucion sol;

    const int n = inst.cantidadNodos();   // incluye al depósito
    const int Q = inst.capacidad();

    // Validación: si algún cliente pide más de lo que cabe en el vehículo,
    // jamás será elegible y el bucle de abajo generaría rutas vacías para
    // siempre. Cortamos acá con un error claro en vez de colgar la app.
    for (int i = 1; i < n; ++i) {
        if (inst.nodo(i).demanda > Q) {
            throw std::invalid_argument(
                "El cliente " + std::to_string(inst.nodo(i).id) +
                " tiene demanda mayor que la capacidad del vehículo (Q).");
        }
    }

    // vector<bool> en vez de std::set<int>: acceso O(1) contiguo en memoria,
    // mejor localidad de caché que los nodos dispersos de un árbol rojo-negro.
    std::vector<bool> visitado(n, false);
    visitado[0] = true;   // el depósito no se "visita" como cliente
    int pendientes = n - 1;

    // Mientras queden clientes sin visitar, construimos una ruta más.
    while (pendientes > 0) {

        Ruta rutaActual;
        // Cota superior real: como cada cliente pide al menos 1 unidad, una
        // ruta no puede tener más de Q clientes (+2 por los depósitos en
        // los extremos). Reservar evita realocaciones/copias por doblado
        // de capacidad a medida que la ruta crece.
        rutaActual.reserve(std::min(n, Q + 2));
        rutaActual.push_back(0);          // arranca en el depósito
        int capacidadRestante = Q;
        int nodoActual        = 0;

        // Vamos llenando la ruta hasta que ya no quepa nadie.
        while (true) {
            int    mejorVecino    = -1;
            double minDistanciaSq = std::numeric_limits<double>::infinity();

            // Buscamos el cliente más cercano cuya demanda entre en la carga.
            // Comparamos distancia al cuadrado: mismo orden que la real, sin sqrt.
            for (int cliente = 1; cliente < n; ++cliente) {
                if (visitado[cliente]) continue;
                int demanda = inst.nodo(cliente).demanda;
                // Pre-filtro: si la demanda no entra en lo que queda de
                // capacidad, ni siquiera calculamos su distancia.
                if (demanda <= capacidadRestante) {
                    double dSq = inst.distanciaCuadrada(nodoActual, cliente);
                    if (dSq < minDistanciaSq) {
                        minDistanciaSq = dSq;
                        mejorVecino    = cliente;
                    }
                }
            }

            // Si no encontramos ningún candidato, cerramos la ruta.
            if (mejorVecino == -1) break;

            // Añadimos el cliente a la ruta.
            rutaActual.push_back(mejorVecino);
            capacidadRestante -= inst.nodo(mejorVecino).demanda;
            visitado[mejorVecino] = true;
            --pendientes;
            nodoActual = mejorVecino;
        }

        // Cerramos la ruta volviendo al depósito.
        rutaActual.push_back(0);
        sol.agregarRuta(rutaActual);
    }

    return sol;
}
