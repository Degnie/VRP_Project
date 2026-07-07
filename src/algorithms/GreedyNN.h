// ============================================================================
//  GreedyNN.h
//  ----------------------------------------------------------------------------
//  Algoritmo Greedy del vecino más cercano (Nearest Neighbor).
//  Complejidad temporal:  O(n^2)
//  Complejidad espacial:  O(n)
// ============================================================================
#ifndef GREEDYNN_H
#define GREEDYNN_H

#include "IVRPSolver.h"

class GreedyNN : public IVRPSolver {
public:
    GreedyNN();

    std::string nombre() const override;
    Solucion    resolver(const Instancia& inst) override;
};

#endif // GREEDYNN_H
