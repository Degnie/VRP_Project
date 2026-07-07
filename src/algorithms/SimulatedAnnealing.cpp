// ============================================================================
//  SimulatedAnnealing.cpp
//  ----------------------------------------------------------------------------
//  Implementación del Recocido Simulado (mismo pseudocódigo del informe).
//
//  Idea:
//    - Empezamos con la solución del Greedy como punto de partida.
//    - En cada iteración generamos una solución vecina con 2-opt.
//    - Si la vecina es mejor, la aceptamos siempre.
//    - Si es peor, la aceptamos con probabilidad p = exp(-delta / T).
//    - Bajamos la temperatura: T = T * alpha.
//    - Nos quedamos con la mejor solución encontrada en TODO el proceso.
// ============================================================================
#include "SimulatedAnnealing.h"
#include "GreedyNN.h"
#include <algorithm>
#include <cmath>
#include <random>

// -----------------------------------------------------------------------------
//  Generador aleatorio único para toda la clase (semilla no determinista).
//  Se declara con "static" para que sea local al archivo.
// -----------------------------------------------------------------------------
static std::mt19937& generador() {
    static std::mt19937 gen(std::random_device{}());
    return gen;
}

// Devuelve un entero aleatorio en [minimo, maximo] (ambos inclusive).
static int randomEntero(int minimo, int maximo) {
    std::uniform_int_distribution<int> dist(minimo, maximo);
    return dist(generador());
}

// Devuelve un real aleatorio en [0.0, 1.0).
static double randomReal() {
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    return dist(generador());
}

// =============================================================================

SimulatedAnnealing::SimulatedAnnealing(double T0, double alpha, double Tmin)
    : m_T0(T0), m_alpha(alpha), m_Tmin(Tmin) {}

void SimulatedAnnealing::setT0(double v)    { m_T0    = v; }
void SimulatedAnnealing::setAlpha(double v) { m_alpha = v; }
void SimulatedAnnealing::setTmin(double v)  { m_Tmin  = v; }

std::string SimulatedAnnealing::nombre() const {
    return "Simulated Annealing (2-opt)";
}

// -----------------------------------------------------------------------------
//  2-opt intra-ruta:
//    Elige una ruta al azar y dos posiciones i < j dentro de esa ruta,
//    e invierte el segmento entre i y j.
//  Esto no cambia la carga total de la ruta, así que no rompe la restricción
//  de capacidad; solo cambia el orden de visita.
// -----------------------------------------------------------------------------
Solucion SimulatedAnnealing::aplicar2Opt(const Solucion& sol) {
    Solucion vecino = sol;   // copia completa (solución original intacta)

    if (vecino.cantidadRutas() == 0) return vecino;

    // 1) Elegir una ruta al azar que tenga al menos 4 elementos (0, a, b, 0).
    //    Menos que eso no admite un 2-opt real.
    std::vector<int> rutasCandidatas;
    for (int i = 0; i < vecino.cantidadRutas(); ++i) {
        if (static_cast<int>(vecino.ruta(i).size()) >= 4) {
            rutasCandidatas.push_back(i);
        }
    }
    if (rutasCandidatas.empty()) return vecino;

    int idxRuta = rutasCandidatas[randomEntero(0, static_cast<int>(rutasCandidatas.size()) - 1)];
    Ruta& r = vecino.ruta(idxRuta);

    // 2) Elegir i, j dentro de la ruta (sin incluir los depósitos de los extremos).
    //    r tiene forma [0, c1, c2, ..., ck, 0]. Trabajamos entre 1 y size-2.
    int i = randomEntero(1, static_cast<int>(r.size()) - 3);
    int j = randomEntero(i + 1, static_cast<int>(r.size()) - 2);

    // 3) Invertir el segmento [i, j].
    std::reverse(r.begin() + i, r.begin() + j + 1);

    return vecino;
}

// -----------------------------------------------------------------------------

Solucion SimulatedAnnealing::resolver(const Instancia& inst) {
    // 1) Solución inicial: la generamos con Greedy.
    GreedyNN greedy;
    Solucion actual = greedy.resolver(inst);
    Solucion mejor  = actual;

    double T = m_T0;

    // 2) Bucle principal de enfriamiento.
    while (T > m_Tmin) {

        // Generar solución vecina con 2-opt.
        Solucion vecino = aplicar2Opt(actual);

        // Calcular la diferencia de costo.
        double costoActual = actual.costoTotal(inst);
        double costoVecino = vecino.costoTotal(inst);
        double delta       = costoVecino - costoActual;

        // Criterio de aceptación.
        if (delta < 0.0) {
            // El vecino es mejor: lo aceptamos siempre.
            actual = vecino;

            // ¿Es también mejor que el mejor histórico?
            if (costoVecino < mejor.costoTotal(inst)) {
                mejor = vecino;
            }
        } else {
            // El vecino es peor: lo aceptamos con probabilidad p.
            double p = std::exp(-delta / T);
            if (randomReal() < p) {
                actual = vecino;
            }
        }

        // Enfriamiento geométrico.
        T = T * m_alpha;
    }

    return mejor;
}
