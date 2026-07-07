// ============================================================================
//  SimulatedAnnealing.h
//  ----------------------------------------------------------------------------
//  Metaheurística de Recocido Simulado con vecindad 2-opt intra-ruta.
//  Complejidad temporal:  O(N_iter)  ~  O(1) respecto a n con delta incremental.
//  Complejidad espacial:  O(n)
//
//  Parámetros por defecto (según el informe):
//      T0    = 1000.0
//      alpha = 0.995
//      Tmin  = 0.01
// ============================================================================
#ifndef SIMULATEDANNEALING_H
#define SIMULATEDANNEALING_H

#include "IVRPSolver.h"

class SimulatedAnnealing : public IVRPSolver {
public:
    SimulatedAnnealing(double T0    = 1000.0,
                       double alpha = 0.995,
                       double Tmin  = 0.01);

    // Setters por si se quieren cambiar los parámetros desde la GUI.
    void setT0(double v);
    void setAlpha(double v);
    void setTmin(double v);

    std::string nombre() const override;
    Solucion    resolver(const Instancia& inst) override;

private:
    double m_T0;
    double m_alpha;
    double m_Tmin;

    // Aplica un intercambio 2-opt sobre una ruta elegida al azar.
    // Devuelve una NUEVA solución vecina (no modifica la original).
    Solucion aplicar2Opt(const Solucion& sol);
};

#endif // SIMULATEDANNEALING_H
