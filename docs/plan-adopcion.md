# Plan de Adopción de Especificaciones VRP

Este documento registra los acuerdos metodológicos consolidados tras la adopción del sistema existente y su vinculación con la nueva especificación del comportamiento.

## 1. Tabla de Mapeo de la Suite de Pruebas

| Archivo / Clase / Test | Clasificación | ID de Regla / Comentario |
| :--- | :--- | :--- |
| **`test_models.py` (Dominio Core)** | | |
| `TestCoordinate::*` (3 tests) | `[MAPEADO]` | RN-012 |
| `TestCliente::*` (4 tests) | `[MAPEADO]` | RN-001 |
| `TestDepositoFlota::*` (3 tests) | `[MAPEADO]` | RN-012, RN-002 |
| `TestInstancia::*` (4 tests) | `[MAPEADO]` | RN-005, RN-006, RN-004 |
| `TestRuta::*` (3 tests) | `[MAPEADO]` | RN-007, RN-008 |
| `TestSolucion::*` (4 tests) | `[MAPEADO]` | RN-009, RN-010, RN-011 |
| `TestDistanciaEuclidiana::*` (3 tests) | `[MAPEADO]` | Parte implícita algorítmica |
| **`test_api_integration.py`** | | |
| `TestConfiguration::*`, `TestPersistenceAdapters::*` | `[SOBRE-ESPECIFICADO]` | Verificar variables de entorno / creación pura. Candidatos a eliminar. |
| `TestAPIFactory::*` (3 tests) | `[PENDIENTE]` | Instanciación FastAPI. |
| `TestSolveEndpoint::test_solve_with_minimal_instance` | `[MAPEADO]` | CU-001 |
| `TestSolveEndpoint::test_solve_rejects_out_of_range_*` | `[MAPEADO]` | RN-012 |
| `TestSolveEndpoint::test_solve_rejects_contact_field...` | `[MAPEADO]` | EC-002 |
| `TestSolveEndpoint::test_solve_rejects_client_exceeding...`| `[MAPEADO]` | RN-006 |
| `TestSolveEndpoint::test_solve_requires_auth` | `[MAPEADO]` | CU-002 |
| `TestSolveEndpoint::test_instances_list_endpoint` | `[MAPEADO]` | CU-003 |
| `TestEndToEndFlow::test_solve_instance_workflow` | `[MAPEADO]` | CU-001 |
| `TestEndToEndFlow::test_solve_instance_client_at_depot` | `[MAPEADO]` | EC-001 |
| **Módulos Adicionales (Revelados)** | | |
| `test_auth.py` | `[REVELA REGLA]` | RN-AUTH-001 |
| `test_coverage_zone_api.py` | `[REVELA REGLA]` | CU-COV-001, RN-COV-001 |
| `test_export.py` | `[REVELA REGLA]` | CU-EXP-001, RN-EXP-001 |
| `test_vehicle_catalog_api.py` | `[REVELA REGLA]` | CU-CAT-001, RN-CAT-001/002 |
| **Optimización y C++ Core** | | |
| `test_optimizers.py::TestSimulatedAnnealing`, `TestLocal` | `[SOBRE-REFINADO]` | Cálculo porcentual Python, innecesario con Core C++. Candidatos a eliminar. |
| `TestCostMatrixFallback::*` | `[MAPEADO]` | RN-MAT-001 |
| `test_osrm_client.py` | `[PENDIENTE]` | Integración técnica. |
| `test_persistence.py` | `[PENDIENTE]` | Adaptadores base de datos. |
| `core_cpp/tests/*` | `[PENDIENTE]` | Suite nativa C++. |

## 2. Tests a Eliminar
* **`[SOBRE-REFINADO]`** (`TestSimulatedAnnealing::*`, `TestLocalOperators::*` en `test_optimizers.py`): Estos tests afirman el cálculo matemático intermedio de la mejora porcentual en Python de 2-opt. Como el optimizador crítico está ahora en C++, verificar esta mejora paso a paso en Python no aporta al dominio; la validación real es que la solución cumpla viabilidad, lo que ya está testeado en los flujos principales.
* **`[SOBRE-ESPECIFICADO]`** (`TestConfiguration::*`, `TestPersistenceAdapters::*` en `test_api_integration.py`): Reafirman que `os.getenv` cargue una URL o que una clase vacía se puede instanciar sin conexión. Aportan fragilidad ante cualquier refactor en la forma de cargar la configuración, y no testean comportamiento de dominio útil observable.

## 3. Cuarentena de Tests (`[PENDIENTE]`)
El resto de pruebas de integración de base de datos (`test_persistence.py`), integración directa de servicio (`test_osrm_client.py`), instanciación del Factory app (`TestAPIFactory`), y los algoritmos matemáticos en C++ (`core_cpp/tests/*`), se mantendrán vigentes y vivos pero en estado de cuarentena lógica frente a la especificación de negocio (no mapean a una RN particular, pero validan el mecanismo técnico profundo). Esta lista representa deuda técnica conocida, y su cantidad **no puede aumentar** en el futuro con nuevos tests de este tipo.

## 4. Contrato de Verify
El sistema se auditará y verificará continuamente usando las herramientas actuales del Makefile, sin introducir utilidades ajenas.
Ejecución:
- `make test` para Python (pytest)
- `make test-cpp` para C++ nativo (ctest)

## 5. Umbral de Mutación Realista
No se impondrá un límite estricto arbitrario (e.g. 95% o 100%).
La ordenanza es: **Medir el Mutation Score actual** tras la adopción (e.g., con `mutmut`), y establecer el umbral configurado de CI en un **2% por debajo** de ese score base. El umbral será orgánico y se elevará progresivamente conforme se refactoricen o añadan implementaciones bajo TDD.

## 6. Línea de Corte (Amnistía de Historial)
> **Directiva de Historial:** La evidencia estricta del ciclo TDD (test-antes-que-código, commits incrementales rojo/verde/refactor) regirá única y exclusivamente a partir del commit en el que se consolide esta adopción. El código y los tests escritos con anterioridad a esta fecha no poseen (ni podrían poseer) este historial. Queda estrictamente prohibido auditar retrospectivamente el código heredado en busca de ciclos TDD faltantes. Cualquier hallazgo falso positivo sobre código histórico será descartado de inmediato.
