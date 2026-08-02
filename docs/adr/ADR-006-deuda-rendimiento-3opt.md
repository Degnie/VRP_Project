# ADR-006: Deuda Técnica de Rendimiento — Construcción de CostMatrix (RNF-001/002/003)

**Fecha:** 2026-08-01 (corrección de diagnóstico y resolución: 2026-08-02)
**Estado:** Resuelto
**Relacionado con:** ADR-0001 (arquitectura híbrida Python/C++)

---

## Contexto

**Corrección de diagnóstico (2026-08-02):** la versión original de este ADR
atribuía la deuda al operador 3-opt sin límite de tiempo/escala. Un
perfilado con timing real por etapa (instancia de 5,000 clientes, bindings
C++ reales, sin ruido de red OSRM) descartó esa hipótesis:

| Etapa | Tiempo medido | % del total |
|---|---|---|
| Construcción del grafo (C++) | 0.03s | 0.03% |
| **Construcción de `CostMatrix` (Python, `solver_orchestrator.py`)** | **83.94s** | **98.4%** |
| NearestNeighbor (C++) | 1.26s | 1.5% |
| SimulatedAnnealing (C++) | 0.07s | 0.08% |
| ThreeOpt (C++, todas las rutas) | 0.01s | 0.02% |

Ni 3-opt ni SimulatedAnnealing son el cuello de botella — ambos son
insignificantes en tiempo absoluto. La causa real es el doble bucle Python
que llena `CostMatrix` celda por celda (`_solve_cpp_pipeline`,
`solver_orchestrator.py`, aprox. líneas 244-247):

```python
for i, from_real_id in enumerate(real_node_ids):
    for j, to_real_id in enumerate(real_node_ids):
        if i != j:
            cost_matrix.set_cost(i, j, cost_lookup[(from_real_id, to_real_id)])
```

Para 5,000 clientes esto son ~25 millones de llamadas a `set_cost`, cada una
cruzando la frontera Python↔C++ vía pybind11 — el overhead de esa frontera
por llamada individual domina el tiempo total, no el cálculo de costos en sí
ni ningún algoritmo de optimización.

Medido en esta máquina, con bindings C++ reales y sin ruido de red OSRM
(`OSRM_URL` aislado vía monkeypatch), tiempo total del pipeline:

| RNF | Escala | Umbral SPEC | Medido |
|---|---|---|---|
| RNF-001 | 50 clientes | 10-50ms | ~50ms (al límite) |
| RNF-002 | 500 clientes | 100-500ms | ~1,054ms (~2x el umbral) |
| RNF-003 | 5,000 clientes | 1-5s | ~443s / ~85s en la corrida de perfilado (~90x el umbral, con varianza entre corridas) |

## Decisión

Se declaró como deuda técnica inicialmente. No se infló artificialmente los
RNF del SPEC para que las pruebas pasaran mientras la deuda estuvo abierta.

**Resuelta en 2026-08-02 (P-01, `docs/PENDIENTES.md`):**
- `core_cpp/include/cost_matrix.hpp`: nuevo método `CostMatrix::set_costs_bulk`
  — llena la matriz completa desde un buffer plano en una sola pasada C++, en
  vez de `N²` llamadas individuales a `set_cost`.
- `core_cpp/src/bindings.cpp`: expone `set_costs_bulk` recibiendo un
  `numpy.ndarray` 2D contiguo vía `py::array_t<double>` — una sola travesía
  de la frontera pybind11 en vez de `N²`.
- `backend_python/service/solver_orchestrator.py`: `_build_cost_lookup`
  (dict, usado por el fallback Python) y `_solve_cpp_pipeline` (pipeline C++)
  ahora derivan ambos de `_build_cost_matrix_array`, que construye la matriz
  como array NumPy denso una sola vez (vectorizado con NumPy para el caso
  euclídeo) — eliminando el dict intermedio de 25M+ entradas que antes se
  reconstruía para instancias grandes.
- `tests/performance/test_rnf_thresholds.py`: los 3 tests recuperan su assert
  real de umbral (`elapsed < threshold`), ya no `spec: PENDIENTE`.
- `SPEC.md` §8: RNF-001/002/003 ya no llevan `[DEUDA TÉCNICA]`.

## Consecuencias

Medido en esta máquina tras el fix (bindings C++ reales, sin ruido de red
OSRM):

| RNF | Escala | Umbral SPEC | Antes | Después |
|---|---|---|---|---|
| RNF-001 | 50 clientes | 10-50ms | ~50ms (al límite) | **~29ms** ✅ |
| RNF-002 | 500 clientes | 100-500ms | ~1,054ms (~2x el umbral) | **~78ms** ✅ |
| RNF-003 | 5,000 clientes | 1-5s | ~443s (~90x el umbral) | **~2.2s** ✅ |

Los tres umbrales se cumplen con margen. No se tocaron los operadores de
búsqueda local (2-opt, 3-opt, SimulatedAnnealing) — el perfilado confirmó
que nunca fueron la causa.
