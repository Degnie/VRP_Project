// ============================================================================
//  Solucion.h
//  ----------------------------------------------------------------------------
//  Representa una solución del VRP: una lista de rutas.
//  Cada ruta es una secuencia de ids de nodos que empieza y termina en 0.
//  Ejemplo:
//      Ruta 1: 0 -> 3 -> 7 -> 0
//      Ruta 2: 0 -> 2 -> 5 -> 1 -> 0
// ============================================================================
#ifndef SOLUCION_H
#define SOLUCION_H

#include "Instancia.h"
#include <vector>

// Una ruta es simplemente una secuencia de ids de nodos.
using Ruta = std::vector<int>;

class Solucion {
public:
    Solucion();

    // Agrega una ruta a la solución.
    void agregarRuta(const Ruta& r);

    // Acceso a rutas.
    int          cantidadRutas() const;
    const Ruta&  ruta(int i)     const;
    Ruta&        ruta(int i);
    const std::vector<Ruta>& rutas() const;

    // Costo total = suma de las distancias de todos los arcos de todas las rutas.
    double costoTotal(const Instancia& inst) const;

    // Verifica que la solución respete las restricciones:
    //   1) cada cliente aparece exactamente una vez,
    //   2) cada ruta comienza y termina en el depósito,
    //   3) la carga de cada ruta no excede la capacidad Q.
    bool esValida(const Instancia& inst) const;

    // Elimina rutas vacías (rutas con solo el depósito de ida y vuelta).
    void eliminarRutasVacias();

    // Vacía la solución completa.
    void limpiar();

private:
    std::vector<Ruta> m_rutas;
};

#endif // SOLUCION_H
