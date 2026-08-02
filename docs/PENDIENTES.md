# Pendientes

Última curaduría: 2026-08-02 · Curadurías realizadas: 2

## Lote en curso
| ID | Ítem | Clase | Procedencia | Curadurías sobrevividas |
|---|---|---|---|---|

## Backlog ordenado
| ID | Ítem | Clase | Procedencia | Curadurías sobrevividas |
|---|---|---|---|---|
| P-03 | Tests técnicos y de integración pendientes de mapeo o en cuarentena | `[DEUDA DE SUITE]` | `tests/unit/test_persistence.py`, `test_api_integration.py`, etc | 1 |
| P-04 | Fixtures faltantes para instancias medianas/masivas | `[DEUDA DE SUITE]` | `tests/conftest.py:54,60` | 1 |

## Decisiones pendientes de tomar
| Ítem | Opciones | Procedencia |
|---|---|---|
| Integrar política DRL para optimización (v0.2) | ¿Invertir en DRL o mantener heurísticas deterministas? | `docs/adr/0003-drl-parameter-calibration.md:123` |
| Cobertura geográfica más allá de Perú | ¿Incluir mapas de otros países en la imagen OSRM? | `CHANGELOG.md` |
| Lógica de reintentos de conexión a BD | ¿Añadir resiliencia de red o mantener fallo rápido? | `PHASE_3_FINAL_STATUS.md:193` |
| Validación nativa extra en C++ `solution.hpp` | ¿Validar a nivel de bindings o en el core puro? | `core_cpp/include/solution.hpp:25` |

## Cerrados
| Ítem | Motivo del cierre | Fecha |
|---|---|---|
| P-01 — Degradación del operador 3-opt en instancias masivas | Diagnóstico original incorrecto (no era 3-opt); perfilado real identificó la causa en la construcción de `CostMatrix` celda por celda vía pybind11 (98.4% del tiempo). Resuelto con `CostMatrix::set_costs_bulk` + `_build_cost_matrix_array` (array NumPy denso, sin dict intermedio). RNF-001/002/003 cumplen umbral tras el fix (~29ms, ~78ms, ~2.2s). Ver ADR-006. | 2026-08-02 |
| P-02 — Tests funcionales de RNF en cuarentena | `tests/performance/test_rnf_thresholds.py` recuperó sus asserts reales de umbral tras P-01; ya no `spec: PENDIENTE`. | 2026-08-02 |
