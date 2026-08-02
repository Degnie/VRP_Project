# Pendientes

Última curaduría: 2026-08-02 · Curadurías realizadas: 1

## Lote en curso
| ID | Ítem | Clase | Procedencia | Curadurías sobrevividas |
|---|---|---|---|---|
| P-01 | Degradación inaceptable del operador 3-opt en instancias masivas (Falla RNF-001, RNF-002, RNF-003) | `[BUG]` | `TESTING_STRATEGY.md` y `ADR-006` | 0 |
| P-02 | Tests funcionales de RNF en cuarentena (habilitar tras corregir P-01) | `[DEUDA DE SUITE]` | `tests/performance/test_rnf_thresholds.py` | 0 |

## Backlog ordenado
| ID | Ítem | Clase | Procedencia | Curadurías sobrevividas |
|---|---|---|---|---|
| P-03 | Tests técnicos y de integración pendientes de mapeo o en cuarentena | `[DEUDA DE SUITE]` | `tests/unit/test_persistence.py`, `test_osrm_client.py`, `test_api_integration.py`, `test_optimizers.py` | 0 |
| P-04 | Fixtures de prueba faltantes para instancias medianas y masivas | `[DEUDA DE SUITE]` | `tests/conftest.py:54,60` | 0 |

## Decisiones pendientes de tomar
| Ítem | Opciones | Procedencia |
|---|---|---|
| Integrar política DRL para optimización (v0.2) | ¿Invertir en machine learning o mantener heurísticas deterministas? | `docs/adr/0003-drl-parameter-calibration.md:123` |
| Cobertura geográfica más allá de Perú | ¿Incluir mapas de otros países en la imagen OSRM? | `CHANGELOG.md` (Rechazado/Descartado) |
| Lógica de reintentos de conexión a BD | ¿Añadir resiliencia de red o mantener fallo rápido (MVP)? | `PHASE_3_FINAL_STATUS.md:193` |
| Validación nativa extra en C++ `solution.hpp` | ¿Validar a nivel de bindings o en el core puro? | `core_cpp/include/solution.hpp:25` |

## Cerrados
| Ítem | Motivo del cierre | Fecha |
|---|---|---|
