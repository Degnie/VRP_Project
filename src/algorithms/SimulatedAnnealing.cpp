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
#include <vector>

// -----------------------------------------------------------------------------
//  Generador aleatorio: uno POR HILO (thread_local), no compartido.
//  std::mt19937 no es thread-safe; si dos SA corren a la vez en dos QThreads
//  (p.ej. GUI lanzando varias corridas), un generador global compartido
//  produciría carreras de datos. thread_local da una instancia independiente
//  por hilo sin necesidad de locks.
// -----------------------------------------------------------------------------
static std::mt19937& generador() {
    thread_local std::mt19937 gen(std::random_device{}());
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
//  2-opt intra-ruta con delta O(1):
//    Ruta r = [0, ..., r[i-1], r[i], ..., r[j], r[j+1], ..., 0].
//    Invertir [i, j] rompe las aristas (r[i-1],r[i]) y (r[j],r[j+1]) y crea
//    (r[i-1],r[j]) y (r[i],r[j+1]). El resto de la ruta no cambia de costo,
//    así que el delta es la diferencia de esas 4 distancias — nada de
//    recorrer la ruta ni la solución completa.
// -----------------------------------------------------------------------------
double SimulatedAnnealing::aplicar2Opt(const Instancia& inst, Solucion& sol,
                                        int& idxRuta, int& i, int& j) {
    if (sol.cantidadRutas() == 0) return 0.0;

    // 1) Elegir una ruta al azar que tenga al menos 4 elementos (0, a, b, 0).
    std::vector<int> rutasCandidatas;
    for (int r = 0; r < sol.cantidadRutas(); ++r) {
        if (static_cast<int>(sol.ruta(r).size()) >= 4) {
            rutasCandidatas.push_back(r);
        }
    }
    if (rutasCandidatas.empty()) return 0.0;

    idxRuta = rutasCandidatas[randomEntero(0, static_cast<int>(rutasCandidatas.size()) - 1)];
    Ruta& r = sol.ruta(idxRuta);

    // 2) Elegir i, j dentro de la ruta (sin incluir los depósitos de los extremos).
    i = randomEntero(1, static_cast<int>(r.size()) - 3);
    j = randomEntero(i + 1, static_cast<int>(r.size()) - 2);

    // 3) Delta real de las 2 aristas que cambian.
    double antes   = inst.distancia(r[i - 1], r[i]) + inst.distancia(r[j], r[j + 1]);
    double despues = inst.distancia(r[i - 1], r[j]) + inst.distancia(r[i], r[j + 1]);

    // 4) Mutar in-place. El caller revierte con el mismo reverse si rechaza.
    std::reverse(r.begin() + i, r.begin() + j + 1);

    return despues - antes;
}

// -----------------------------------------------------------------------------

Solucion SimulatedAnnealing::resolver(const Instancia& inst) {
    // 1) Solución inicial: la generamos con Greedy.
    GreedyNN greedy;
    Solucion actual = greedy.resolver(inst);
    Solucion mejor  = actual;

    // Costo se mantiene incremental (O(1) por movimiento), no se recalcula
    // recorriendo toda la solución en cada iteración.
    double costoActual = actual.costoTotal(inst);
    double costoMejor   = costoActual;

    double T = m_T0;

    // 2) Bucle principal de enfriamiento.
    while (T > m_Tmin) {

        int idxRuta = -1, i = -1, j = -1;
        double delta = aplicar2Opt(inst, actual, idxRuta, i, j);

        if (idxRuta == -1) {
            // No había ninguna ruta elegible para 2-opt; nada que hacer.
            T = T * m_alpha;
            continue;
        }

        bool aceptar = (delta < 0.0) || (randomReal() < std::exp(-delta / T));

        if (aceptar) {
            costoActual += delta;
            if (costoActual < costoMejor) {
                mejor      = actual;
                costoMejor = costoActual;
            }
        } else {
            // Revertir: invertir el mismo segmento lo deja como estaba.
            Ruta& r = actual.ruta(idxRuta);
            std::reverse(r.begin() + i, r.begin() + j + 1);
        }

        // Enfriamiento geométrico.
        T = T * m_alpha;
    }

    return mejor;
}
