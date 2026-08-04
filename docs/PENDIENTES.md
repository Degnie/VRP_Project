# Pendientes

Última curaduría: 2026-08-04 · Curadurías realizadas: 4

## Lote en curso
| ID | Ítem | Clase | Procedencia | Curadurías sobrevividas |
|---|---|---|---|---|

## Backlog ordenado
| ID | Ítem | Clase | Procedencia | Curadurías sobrevividas |
|---|---|---|---|---|

## Decisiones pendientes de tomar
| Ítem | Opciones | Procedencia |
|---|---|---|

## Cerrados
| Ítem | Motivo del cierre | Fecha |
|---|---|---|
| P-01 — Degradación del operador 3-opt en instancias masivas | Diagnóstico original incorrecto (no era 3-opt); perfilado real identificó la causa en la construcción de `CostMatrix` celda por celda vía pybind11 (98.4% del tiempo). Resuelto con `CostMatrix::set_costs_bulk` + `_build_cost_matrix_array` (array NumPy denso, sin dict intermedio). RNF-001/002/003 cumplen umbral tras el fix (~29ms, ~78ms, ~2.2s). Ver ADR-006. | 2026-08-02 |
| P-02 — Tests funcionales de RNF en cuarentena | `tests/performance/test_rnf_thresholds.py` recuperó sus asserts reales de umbral tras P-01; ya no `spec: PENDIENTE`. | 2026-08-02 |
| Integrar política DRL para optimización (v0.2) | Decisión del usuario: mantener heurísticas deterministas (`_compute_sa_params` en `solver_orchestrator.py`). Sin evidencia de que la calidad de solución actual sea un problema reportado — invertir en DRL (dataset de entrenamiento, infraestructura, PyTorch en runtime) es especulativo sin necesidad concreta. Revisar si en el futuro hay quejas de calidad de ruta. | 2026-08-02 |
| Cobertura geográfica más allá de Perú | Decisión del usuario: mantener solo Perú — el negocio apunta a mercados locales. Ampliar a otro país es mecánico (`make osrm-prepare` con otro extracto de Geofabrik), sin cambio de arquitectura, así que queda disponible para cuando haya demanda real. | 2026-08-02 |
| Lógica de reintentos de conexión a BD | Ítem obsoleto — ya resuelto en `0.3.6` (ver `CHANGELOG.md`). `postgres_adapter.py`/`mongodb_adapter.py` ya implementan reintentos con backoff (`CONNECT_RETRIES`). Referenciaba `PHASE_3_FINAL_STATUS.md`, documento de una fase temprana nunca resincronizado con el estado real del código. | 2026-08-02 |
| Validación nativa extra en C++ `solution.hpp` | Decisión del usuario: eliminar el falso `Solution::is_valid()` (stub que siempre devolvía `true`) en vez de implementar una segunda capa de validación — la validación real de invariantes ya vive en Python (`Solucion.__post_init__`), con mensajes de error en español ya cuidados. Ver commit correspondiente. | 2026-08-02 |
| P-03 — Tests técnicos y de integración pendientes de mapeo o en cuarentena | `TestSolverPipeline`, `TestAPIFactory` y `test_osrm_client.py` documentados como cuarentena técnica permanente; `TestFleetSizeValidation` mapeado a RN-013; `test_python_fallback_produces_feasible_solution` mapeado a RN-011/RN-005/RN-010. Ningún `spec: PENDIENTE` queda en la suite. Ver commit `fa15f78`. | 2026-08-02 |
| P-04 — Fixtures faltantes para instancias medianas/masivas | `small_instance`/`medium_instance`/`large_instance` en `tests/conftest.py` eran placeholders huérfanos de un modelo de dominio incompatible (dos eran literalmente `return None`), sin uso real en la suite — se eliminaron en vez de completarse. Ver commit `df3b182`. | 2026-08-02 |
| P-05 — `test_persistence.py` en cuarentena (`spec: PENDIENTE`) | Los 9 tests ya pasaban contra PostgreSQL/MongoDB reales — la cuarentena era defensiva, no encubría un fallo. Ninguno citaba una regla de SPEC formal; se propusieron y aprobaron RN-021 (round-trip sin pérdida) y RN-022 (reconexión automática) antes de destrackear. Sin cambios de código de producción. Ver commits `43c6629`, `5ed2dcd`. | 2026-08-04 |
