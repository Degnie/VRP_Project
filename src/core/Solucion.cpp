// ============================================================================
//  Solucion.cpp
// ============================================================================
#include "Solucion.h"
#include <stdexcept>

Solucion::Solucion() {}

void Solucion::agregarRuta(const Ruta& r) {
    m_rutas.push_back(r);
}

int Solucion::cantidadRutas() const {
    return static_cast<int>(m_rutas.size());
}

const Ruta& Solucion::ruta(int i) const {
    if (i < 0 || i >= static_cast<int>(m_rutas.size())) {
        throw std::out_of_range("Indice de ruta fuera de rango.");
    }
    return m_rutas[i];
}

Ruta& Solucion::ruta(int i) {
    if (i < 0 || i >= static_cast<int>(m_rutas.size())) {
        throw std::out_of_range("Indice de ruta fuera de rango.");
    }
    return m_rutas[i];
}

const std::vector<Ruta>& Solucion::rutas() const {
    return m_rutas;
}

double Solucion::costoTotal(const Instancia& inst) const {
    // Recorre cada ruta y suma la distancia entre nodos consecutivos.
    double total = 0.0;
    for (int i = 0; i < static_cast<int>(m_rutas.size()); ++i) {
        const Ruta& r = m_rutas[i];
        for (int k = 0; k + 1 < static_cast<int>(r.size()); ++k) {
            total += inst.distancia(r[k], r[k + 1]);
        }
    }
    return total;
}

bool Solucion::esValida(const Instancia& inst) const {
    // 1) Cada cliente aparece exactamente una vez en toda la solución.
    // vector<bool> indexado por id: O(1) por chequeo/inserción y sin la
    // fragmentación de heap de un std::set (nodo por nodo, con punteros).
    std::vector<bool> vistos(inst.cantidadNodos(), false);
    int totalVistos = 0;

    for (int i = 0; i < static_cast<int>(m_rutas.size()); ++i) {
        const Ruta& r = m_rutas[i];

        // 2) Cada ruta comienza y termina en el depósito (id 0).
        if (r.size() < 2)             return false;
        if (r.front() != 0)           return false;
        if (r.back()  != 0)           return false;

        // 3) Verificar carga acumulada de la ruta.
        int carga = 0;
        for (int k = 1; k + 1 < static_cast<int>(r.size()); ++k) {
            int idCliente = r[k];
            if (idCliente < 0 || idCliente >= static_cast<int>(vistos.size())) return false;
            if (vistos[idCliente]) return false;   // duplicado
            vistos[idCliente] = true;
            ++totalVistos;
            carga += inst.nodo(idCliente).demanda;
        }
        if (carga > inst.capacidad()) return false;
    }

    // 4) La cantidad de clientes visitados debe coincidir con el total.
    if (totalVistos != inst.cantidadClientes()) return false;

    return true;
}

void Solucion::eliminarRutasVacias() {
    std::vector<Ruta> filtradas;
    for (int i = 0; i < static_cast<int>(m_rutas.size()); ++i) {
        // Una ruta "vacía" es una que solo contiene [0, 0].
        if (m_rutas[i].size() > 2) filtradas.push_back(m_rutas[i]);
    }
    m_rutas = filtradas;
}

void Solucion::limpiar() {
    m_rutas.clear();
}
