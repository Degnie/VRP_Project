// ============================================================================
//  Instancia.h
//  ----------------------------------------------------------------------------
//  Contiene todos los datos de un caso del problema:
//    - Lista de nodos (posición 0 = depósito, resto = clientes).
//    - Capacidad máxima del vehículo (Q).
//  Provee además el cálculo de la distancia euclidiana entre dos nodos.
// ============================================================================
#ifndef INSTANCIA_H
#define INSTANCIA_H

#include "Cliente.h"
#include <string>
#include <vector>

class Instancia {
public:
    Instancia();

    // Agrega un nodo. Si el vector está vacío, ese nodo se toma como depósito.
    void agregarNodo(const Cliente& c);

    // Getters básicos.
    int             cantidadClientes() const;   // Sin contar el depósito.
    int             cantidadNodos()    const;   // Con el depósito.
    int             capacidad()        const;
    const Cliente&  depot()            const;   // Nodo 0.
    const Cliente&  nodo(int i)        const;   // Cualquier nodo por índice.

    // Setter simple.
    void setCapacidad(int Q);
    void setNombre(const std::string& n);
    const std::string& nombre() const;

    // Distancia euclidiana entre los nodos i y j.
    // Se calcula on-the-fly (no se guarda matriz) para poder escalar a n grande.
    double distancia(int i, int j) const;

    // Distancia al cuadrado (sin sqrt). Usar en comparaciones de heurísticas
    // (p.ej. buscar el vecino más cercano); el orden relativo es el mismo
    // porque sqrt es monótona creciente, y nos ahorramos la raíz.
    double distanciaCuadrada(int i, int j) const;

    // Vacía todos los datos (útil al cargar una nueva instancia).
    void limpiar();

private:
    std::string          m_nombre;
    int                  m_capacidad;
    std::vector<Cliente> m_nodos;   // Posición 0 = depósito.
};

#endif // INSTANCIA_H
