# ADR-006: Deuda Técnica de Rendimiento en 3-opt (RNF-001/002/003)

**Fecha:** 2026-08-01
**Estado:** Aceptado
**Relacionado con:** ADR-0001 (arquitectura híbrida Python/C++)

---

## Contexto

En la migración a C++, la optimización final (3-opt) no implementa límites de
tiempo rígidos (time-caps) ni escala sus iteraciones dinámicamente frente al
tamaño de `n`. `solver_orchestrator.py` fija
`max_iters = min(1000, max(100, 50*n))` para el Simulated Annealing previo,
que se satura en 1000 iteraciones para cualquier instancia de 20+ clientes —
el conteo de iteraciones de SA no es la causa. El costo por movimiento del
3-opt posterior sí escala con `n` sin ningún corte, y en instancias >500 nodos
ese costo asfixia el rendimiento prometido por el SPEC.

Medido en esta máquina, con bindings C++ reales y sin ruido de red OSRM
(`OSRM_URL` aislado vía monkeypatch):

| RNF | Escala | Umbral SPEC | Medido |
|---|---|---|---|
| RNF-001 | 50 clientes | 10-50ms | ~50ms (al límite) |
| RNF-002 | 500 clientes | 100-500ms | ~1,054ms (~2x el umbral) |
| RNF-003 | 5,000 clientes | 1-5s | ~443s (~90x el umbral) |

## Decisión

Se declara como deuda técnica. No se inflarán artificialmente los RNF del
SPEC para que las pruebas pasen — quedan marcados `[DEUDA TÉCNICA]` en
`SPEC.md` §8, preservando el estándar aspiracional del producto. Las pruebas
de performance (`tests/performance/test_rnf_thresholds.py`) quedan anotadas
`spec: PENDIENTE` para RNF-001/002/003 en vez de un assert que mienta sobre
cumplimiento.

## Consecuencias / Mitigación futura

La deuda será subsanada en un parche futuro mediante:
- Límites de tiempo estrictos (`time_limit_ms`) a nivel de los operadores C++
  (3-opt, y potencialmente el resto de la búsqueda local).
- Alternativa/complemento: paralelización de la búsqueda local.

Hasta entonces, el sistema es funcionalmente correcto a cualquier escala
(la solución sigue siendo válida) pero no cumple los tiempos de respuesta
aspiracionales del SPEC para instancias medianas/grandes.
