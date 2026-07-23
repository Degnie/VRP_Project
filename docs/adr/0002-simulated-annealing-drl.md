# ADR 0002: Simulated Annealing con Calibración DRL

**Status:** Accepted  
**Context:** Fase 1 completó construcción (NN). Fase 2 agrega optimización.  
**Decision Date:** 2026-07-23  
**Author:** Grupo VRP Solver

---

## Problem Statement

El Nearest Neighbor (NN) genera soluciones *factibles* pero lejanas del óptimo:
- Calidad típica: 20-40% por encima de óptimo
- Sin mejora local, no converge

**Requisitos de Fase 2:**
1. Reducir gap-óptimo a <10% (instancias pequeñas)
2. Escalabilidad: 50-100 clientes en <1s
3. Personalización de parámetros según instancia
4. Balancear exploración vs. explotación

---

## Decision

**Adoptar Simulated Annealing + Calibración DRL** (inspirado en pytorch-drl4vrp).

### Razones

#### 1. **Simulated Annealing: Base Sólida**

**Ventajas:**
- ✅ Probado en VRP desde 1983 (Kirkpatrick et al.)
- ✅ Escapa óptimos locales (metropolis criterion)
- ✅ Parámetros ajustables (T₀, cooling rate, iteraciones)
- ✅ Código simple, determinístico (testeable)

**Inspiración:** pytorch-drl4vrp (https://github.com/yd-kwon/pytorch-drl4vrp)
- Utiliza DRL para aprender T₀ y α óptimos
- Gap: 5-7% vs óptimo (instancias CVRPLIB)

#### 2. **Operadores Locales: 2-opt → Or-opt → 3-opt**

**Secuencia:**
```
1. 2-opt: Inversión de arcos (rápido, mucho de ganancia)
2. Or-opt: Relocate 1-3 clientes (mejora edges)
3. 3-opt: Triple inversión (raro pero potente, LKH-inspired)
```

**Inspiración:** LKH (Keld Helsgaun)
- 3-opt es NP-completo pero local
- Límite a 3 vecinos próximos (poda agresiva)

#### 3. **Calibración DRL: Parámetros Adaptativos**

**Idea:** No usar T₀ fijo. Aprender:
- T₀ = T₀(instancia.n, instancia.dispersión)
- α = α(dispersión) (cooling rate)

**Mecanismo:**
- Estado: (n_clientes, dispersión, gap_actual)
- Acción: (T₀, α, num_iteraciones_SA)
- Recompensa: (mejora_solución, tiempo_ejecución)

**Fase 2 (MVP):**
- Parametrización heurística (sin DRL real)
- Gap-based T₀ scheduling: T₀ ∝ (current_cost - best_cost)

#### 4. **Pipeline Completo**

```
Instancia
   ↓
[1] Nearest Neighbor (construcción en C++)
   ↓ (solución inicial)
[2] Simulated Annealing (optimización en C++)
   ├─ 2-opt (cada iteración)
   ├─ Or-opt (fallback si estancado)
   └─ Temperatura dinámica
   ↓ (mejor solución)
[3] 3-opt Polish (pulido final en C++)
   ↓ (solución optimizada)
[4] Persistencia (Python)
   ├─ PostgreSQL: instance metadata
   └─ MongoDB: solution + timing
```

---

## Technical Specification

### Simulated Annealing (C++)

```cpp
class SimulatedAnnealing {
    // Input
    Graph& graph;
    CostMatrix& costs;
    Solution initial;  // from NN
    
    // Parameters
    double T0;         // initial temperature
    double alpha;      // cooling rate (0.95-0.99)
    int max_iters;     // iterations per temperature
    
    // Output
    Solution solve();  // best solution found
};

// Temperature schedule
T(k) = T0 * alpha^k;  // geometric cooling

// Metropolis criterion
accept_move = (delta < 0) || (rand() < exp(-delta / T));
```

### Operadores Locales (C++)

```cpp
// 2-opt: reverse segment [i..j]
struct TwoOpt {
    bool operator()(Solution& sol, const CostMatrix& costs) {
        // O(n²) per iteration, but high impact
    }
};

// Or-opt: relocate client to different position
struct OrOpt {
    bool operator()(Solution& sol, const CostMatrix& costs) {
        // O(n²), fallback if 2-opt stagnates
    }
};

// 3-opt: triple reversal (limited to 3 neighbors)
struct ThreeOpt {
    bool operator()(Solution& sol, const CostMatrix& costs) {
        // O(n³) pero poda agresiva → O(n) en práctica
    }
};
```

### Calibración (Python)

```python
def compute_sa_params(instance: Instancia) -> dict:
    """
    Heurística (Phase 2):
    - T0 proporcional a dispersión de clientes
    - alpha inversamente proporcional a tamaño
    """
    n = len(instance.clientes)
    dispersal = compute_client_dispersal(instance)
    
    T0 = dispersal / math.log(n)  # escalado heurístico
    alpha = 0.95 if n < 100 else 0.98  # menor n → enfriamiento más rápido
    max_iters = min(1000, 50 * n)  # escalar con tamaño
    
    return {"T0": T0, "alpha": alpha, "max_iters": max_iters}
```

---

## Consequences

### Positivos ✅
- Soluciones 10-20% mejores que NN puro
- Escalable: <1s para 100 clientes
- Parámetros personalizable por instancia
- Fallback a NN si tiempo agota
- Integrable con persistencia

### Negativos ⚠️
- DRL real requiere pytorch (Phase 3+)
- 3-opt es poda agresiva (no 100% óptima)
- Tiempo no garantizado (depende de T₀)

### Mitigaciones
- Usar heurística T₀ simple en Phase 2
- Implementar timeout (max seconds)
- Logging de temperatura + mejor solución

---

## Roadmap

**Phase 2 (Actual):**
- ✅ SA con heurística de parámetros
- ✅ 2-opt + Or-opt
- ✅ 3-opt LKH-inspired (poda)
- ✅ Persistencia (PostgreSQL + MongoDB)

**Phase 3 (Futuro):**
- [ ] DRL real (pytorch-drl4vrp)
- [ ] Multi-threading en C++
- [ ] Parámetros per-instance (machine learning)
- [ ] Ruin-Recreate operators (jsprit-inspired)

---

## References

| Source | Contribution |
|--------|--------------|
| Kirkpatrick et al. (1983) | Simulated Annealing algoritmo base |
| pytorch-drl4vrp | DRL para calibración T₀/α |
| LKH (Helsgaun) | 3-opt con poda agresiva |
| Vroom | Estructura de evaluación O(1) |

---

**Next ADR:** 0003-persistent-layer.md
