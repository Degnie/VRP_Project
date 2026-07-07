// ============================================================================
//  IVRPSolver.h
//  ----------------------------------------------------------------------------
//  Interfaz común para todos los algoritmos que resuelven el VRP.
//  Permite a la GUI trabajar con "un solver" sin importar cuál sea.
// ============================================================================
#ifndef IVRPSOLVER_H
#define IVRPSOLVER_H

#include "../core/Instancia.h"
#include "../core/Solucion.h"
#include <string>

class IVRPSolver {
public:
    virtual ~IVRPSolver() {}

    // Nombre corto del algoritmo (para mostrar en la GUI).
    virtual std::string nombre() const = 0;

    // Resuelve el problema para la instancia dada y devuelve una solución.
    virtual Solucion resolver(const Instancia& inst) = 0;
};

#endif // IVRPSOLVER_H
