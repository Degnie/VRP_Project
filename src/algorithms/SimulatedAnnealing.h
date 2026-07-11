// ============================================================================
//  SimulatedAnnealing.h
//  ----------------------------------------------------------------------------
//  Metaheurística de Recocido Simulado con vecindad 2-opt intra-ruta.
//  Cada movimiento evalúa su costo en O(1): solo mira las dos aristas que
//  cambian, no recalcula el costo total de la solución.
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

    // Elige una ruta y dos posiciones i<j al azar dentro de ella, invierte el
    // segmento [i, j] IN-PLACE sobre 'sol' y devuelve el delta de costo real
    // (solo mirando las 2 aristas rotas y las 2 nuevas, sin recorrer la ruta).
    // Si no hay ninguna ruta elegible, deja 'sol' intacta y devuelve delta=0.
    // idxRuta/i/j quedan seteados con el movimiento aplicado, para poder
    // revertirlo (reversar el mismo segmento) si el caller lo rechaza.
    double aplicar2Opt(const Instancia& inst, Solucion& sol,
                        int& idxRuta, int& i, int& j);
};

#endif // SIMULATEDANNEALING_H
