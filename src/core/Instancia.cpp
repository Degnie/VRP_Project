// ============================================================================
//  Instancia.cpp
// ============================================================================
#include "Instancia.h"
#include <cassert>
#include <cmath>
#include <stdexcept>

Instancia::Instancia() : m_nombre("sin_nombre"), m_capacidad(0) {}

void Instancia::agregarNodo(const Cliente& c) {
    m_nodos.push_back(c);
}

int Instancia::cantidadClientes() const {
    // El depósito no cuenta como cliente.
    if (m_nodos.empty()) return 0;
    return static_cast<int>(m_nodos.size()) - 1;
}

int Instancia::cantidadNodos() const {
    return static_cast<int>(m_nodos.size());
}

int Instancia::capacidad() const {
    return m_capacidad;
}

const Cliente& Instancia::depot() const {
    if (m_nodos.empty()) {
        throw std::runtime_error("La instancia no tiene depósito.");
    }
    return m_nodos[0];
}

const Cliente& Instancia::nodo(int i) const {
    // Método de alto tráfico (Greedy y SA lo llaman en cada comparación de
    // distancia). assert() en vez de throw: en Release (NDEBUG) esto se
    // compila a nada, sin branching extra en el hot-loop; en Debug sigue
    // atrapando índices inválidos igual que antes.
    assert(i >= 0 && i < static_cast<int>(m_nodos.size()) && "Indice de nodo fuera de rango.");
    return m_nodos[i];
}

void Instancia::setCapacidad(int Q) {
    m_capacidad = Q;
}

void Instancia::setNombre(const std::string& n) {
    m_nombre = n;
}

const std::string& Instancia::nombre() const {
    return m_nombre;
}

double Instancia::distancia(int i, int j) const {
    return std::sqrt(distanciaCuadrada(i, j));
}

double Instancia::distanciaCuadrada(int i, int j) const {
    const Cliente& a = nodo(i);
    const Cliente& b = nodo(j);
    double dx = a.x - b.x;
    double dy = a.y - b.y;
    return dx * dx + dy * dy;
}

void Instancia::limpiar() {
    m_nodos.clear();
    m_capacidad = 0;
    m_nombre = "sin_nombre";
}
