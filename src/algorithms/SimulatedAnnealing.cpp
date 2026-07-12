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

    // 1) Elegir una ruta al azar por índice directo (sin construir un vector
    // de candidatas en cada iteración: en un hot-loop de miles de llamadas
    // esa asignación dinámica pesa más que el propio cálculo del delta).
    // Si a la ruta elegida le falta tamaño para un 2-opt real (0,a,b,0),
    // esta iteración simplemente no genera movimiento (idxRuta = -1).
    int candidata = randomEntero(0, sol.cantidadRutas() - 1);
    if (static_cast<int>(sol.ruta(candidata).size()) < 4) return 0.0;

    idxRuta = candidata;
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
    // recorriendo toda la solución en cada iteración (salvo el recálculo
    // periódico de más abajo, para corregir drift de punto flotante).
    double costoActual = actual.costoTotal(inst);
    double costoMejor  = costoActual;

    // Presupuesto de iteraciones REALES (2-opt con ruta elegible) escalado
    // con el tamaño de la instancia: con T0/alpha/Tmin fijos, el enfriamiento
    // por defecto se agota en ~2300 pasos sin importar si n es 10 o 10^6,
    // dejando casi toda una instancia grande sin tocar. Lo acotamos entre un
    // piso (instancias chicas siguen explorando igual que antes) y un techo
    // (para no correr indefinidamente con n = 10^6).
    const long long n = std::max(1, inst.cantidadClientes());
    const long long maxIteracionesReales =
        std::min<long long>(std::max<long long>(2000, n * 20), 2'000'000);

    // Válvula de seguridad: si TODAS las rutas son demasiado cortas para un
    // 2-opt (idxRuta == -1 siempre), esos intentos no cuentan como
    // "reales" y no enfrían nada — sin este tope el bucle no terminaría.
    const long long maxIntentosTotales = maxIteracionesReales * 50;

    // Cada K movimientos ACEPTADOS, se recalcula costoActual desde cero:
    // sumar deltas en punto flotante millones de veces acumula error.
    const long long RECALCULO_CADA = 10000;

    // m_alpha fijo es justamente el "decaimiento ciego" del problema: con
    // alpha=0.995 el enfriamiento llega a Tmin en ~2300 pasos SIEMPRE, sin
    // importar que maxIteracionesReales ahora sea 2 millones para n grande
    // — la condición T > m_Tmin cortaría el bucle mucho antes de agotar el
    // presupuesto. Derivamos el alpha que hace que T tarde exactamente
    // maxIteracionesReales pasos en llegar a Tmin, y usamos el más lento de
    // los dos (así un alpha explícitamente más conservador vía setAlpha()
    // se sigue respetando).
    const double alphaDerivado = std::pow(m_Tmin / m_T0, 1.0 / static_cast<double>(maxIteracionesReales));
    const double alphaEfectivo = std::max(m_alpha, alphaDerivado);

    double T = m_T0;
    long long iteracionesReales = 0;
    long long aceptados         = 0;
    long long intentosTotales   = 0;

    // 2) Bucle principal de enfriamiento.
    while (T > m_Tmin
           && iteracionesReales < maxIteracionesReales
           && intentosTotales < maxIntentosTotales) {
        ++intentosTotales;

        int idxRuta = -1, i = -1, j = -1;
        double delta = aplicar2Opt(inst, actual, idxRuta, i, j);

        if (idxRuta == -1) {
            // Ruta elegida sin tamaño para 2-opt: no se generó ningún
            // movimiento, así que no gastamos temperatura en esta iteración.
            continue;
        }
        ++iteracionesReales;

        // exp(-delta/T): con delta/T muy grande, IEEE 754 ya devuelve 0.0 sin
        // levantar excepciones, pero acotamos el exponente para no depender
        // de ese comportamiento de underflow y evitar el cómputo de más.
        bool aceptar;
        if (delta < 0.0) {
            aceptar = true;
        } else {
            double exponente = -delta / T;
            double p = (exponente < -700.0) ? 0.0 : std::exp(exponente);
            aceptar = randomReal() < p;
        }

        if (aceptar) {
            ++aceptados;
            costoActual += delta;

            if (aceptados % RECALCULO_CADA == 0) {
                costoActual = actual.costoTotal(inst);
            }

            if (costoActual < costoMejor) {
                mejor      = actual;
                costoMejor = costoActual;
            }
        } else {
            // Revertir: invertir el mismo segmento lo deja como estaba.
            Ruta& r = actual.ruta(idxRuta);
            std::reverse(r.begin() + i, r.begin() + j + 1);
        }

        // Enfriamiento geométrico (solo en iteraciones que sí intentaron un 2-opt real).
        T = T * alphaEfectivo;
    }

    return mejor;
}
