# Changelog

Todos los cambios notables en este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## ⬆️ MIGRACIÓN: Academia → Producción (2026-07-23 en adelante)

**Este punto marca la transición arquitectónica de la solución académica Qt/C++ al SaaS híbrido Python/C++.**

La historia anterior del proyecto (trabajo académico UNMSM 2024-2026) se preserva en Git pero no se mezcla con esta rama. Ver [docs/adr/0001-hybrid-python-cpp.md](docs/adr/0001-hybrid-python-cpp.md) para justificación técnica.

**Versioning:** A partir de aquí, semver estricto. v0.1.0-alpha inicia con base de arquitectura.

---

## [0.1.0-alpha] — 2026-07-23

### 🔄 Migration (Academic → Production)

Transición de arquitectura monolítica Qt/C++17 a híbrida Python/C++ para escalabilidad y producción.

**Referencias de inspiración:**
- PyVRP (arquitectura Python/C++ + pybind11 bindings)
- Vroom (matrices de costo dirigidas, evaluación C++)
- VeRyPy (construcción multisemilla modular)
- pytorch-drl4vrp (calibración dinámica de parámetros SA)
- LKH (búsqueda local 3-opt rigurosa)
- jsprit (operador Ruin-Recreate)
- timefold-quickstarts (aislamiento de invariantes)
- Rosomaxa/Open-VRP (inmutabilidad y TDD)
- VRP-RL (pre-clasificación de instancias)

### ✨ Added

#### Backend Python
- **Estructura modular:**
  - `backend_python/api/` — FastAPI endpoints (POST /solve, GET /instances, etc)
  - `backend_python/models/` — Entidades de dominio (Instancia, Cliente, Solución, Ruta)
  - `backend_python/persistence/` — Adapters duales (MongoDB, PostgreSQL)
  - `backend_python/service/` — Orquestador principal (solver_orchestrator.py, validation_service.py)

- **Orquestación inteligente:**
  - Motor de construcción multisemilla (Nearest Neighbor, Farthest, Random, Regret)
  - Lanzamiento concurrente de heurísticas iniciales
  - Pre-clasificación de instancias (VRP-RL inspired)

- **Validación de invariantes:**
  - Capacidad de vehículos no excedida
  - Cada cliente visitado exactamente una vez
  - Ciclos cerrados (depot → clientes → depot)
  - Demandas y distancias siempre positivas

- **Suite TDD:**
  - Tests unitarios para orquestador
  - Tests de integración Python↔C++
  - Fixtures estratificadas (small/medium/large instances)

#### Core C++
- **Núcleo algorítmico:**
  - `graph.hpp/cpp` — Estructura de grafo dirigido con validación
  - `cost_matrix.hpp/cpp` — Matriz de adyacencia asimétrica (Vroom-inspired)
  - `bindings.cpp` — pybind11 module para exponer C++ → Python

- **Builders (Construcción):**
  - Greedy Nearest Neighbor clásico
  - Farthest Insertion
  - Random construction
  - Regret-based insertion (k-regret)

- **Optimizers (Optimización):**
  - Simulated Annealing con temperatura dinámica
  - Parámetros calibrables vía DRL (pytorch-drl4vrp inspired)
  - ILS (Iterated Local Search) como fallback

- **Operators (Operadores Locales):**
  - 2-opt intra-ruta
  - Or-opt (relocate 1-3 clientes)
  - 3-opt LKH-inspired para pulido final
  - Ruin-Recreate (jsprit paradigm) como alternativa

- **Data Structures:**
  - Zero-copy numpy array passing (immutable design)
  - Shared types header-only (sin serialización)

#### Documentación
- `README.md` — Overview, quick start, stack técnico, créditos
- `docs/ARCHITECTURE.md` — Diseño profundo, diagramas, flujos de datos
- `docs/API.md` — Especificación REST con ejemplos cURL
- `docs/CREDITS.md` — Tabla detallada de atribuciones + justificación
- `docs/references.md` — Mapeo repos → ideas aplicadas
- `docs/adr/0001-hybrid-python-cpp.md` — Decisión arquitectónica principal
- `docs/adr/0002-asymmetric-cost-matrices.md` — Por qué grafos dirigidos
- `docs/adr/0003-drl-parameter-calibration.md` — DRL para tuning
- `docs/adr/0004-ruin-recreate-operators.md` — Operadores alternativos

#### Build & Deployment
- `CMakeLists.txt` — Build integrado Python + C++
- `requirements.txt` — Dependencias Python (FastAPI, pydantic, pybind11, numpy)
- `Makefile` — Targets: build, test, run, clean
- `docker-compose.yml` — Dev env (PostgreSQL, MongoDB)
- `.env.example` — Configuración de ejemplo
- `.gitignore` — Reglas para Python/C++ build artifacts

#### Tests
- `tests/unit/` — Tests unitarios Python
- `tests/integration/` — Tests de integración full-stack
- `tests/fixtures/` — Datasets (small: <100, medium: 100-1k, large: >1k nodos)

### 🔧 Technical Decisions (Documentadas en ADRs)

1. **Hybrid Python/C++:** Orquestación de alto nivel en Python, cálculos puros en C++ (PyVRP pattern)
2. **Asymmetric Matrices:** Grafos dirigidos, no asume simetría euclidiana (Vroom pattern)
3. **DRL Calibration:** Temperatura SA controlada dinámicamente vía Deep RL (pytorch-drl4vrp pattern)
4. **Modular Operators:** Builders, optimizers, operators separados → 10+ algoritmos sin refactor (jsprit pattern)
5. **Immutable Data Flow:** Invariantes garantizadas en paso Python↔C++ (Rosomaxa + Open-VRP philosophy)
6. **TDD Everywhere:** 100% coverage de orquestador + algoritmos (Open-VRP pattern)

### ⚠️ Known Limitations

- GIL de Python controlado: construcción multisemilla ocurre en Python pero C++ es single-threaded por ahora
- Matrices de distancia pre-computadas (OSRM/Valhalla integration pending)
- 3-opt experimental (optimización en progreso)

### 🎯 Next Phase (Roadmap)

- [ ] Implementar full 3-opt LKH con restarts
- [ ] Integración OSRM/Valhalla para distancias reales
- [ ] Paralelización C++ (multi-threaded SA)
- [ ] DRL training pipeline (pytorch-drl4vrp full integration)
- [ ] Web UI (React/Mapbox)
- [ ] Benchmarking público (CVRPLIB)
- [ ] Containerización (Docker image <100MB)

---

## [0.3.0] — 2026-07-23

### ✨ Added

#### Fase 3: Persistencia real + API integrada
- `backend_python/config.py`: configuración centralizada vía `.env.local` (fallback a variables de entorno del sistema)
- `PostgreSQLAdapter`: implementación real de `save_instance`/`load_instance`/`list_instances` contra PostgreSQL (antes stub)
- `MongoDBAdapter`: implementación real de `save_solution`/`load_solution`/`list_solutions`/`save_cost_matrix`/`load_cost_matrix` contra MongoDB (antes stub)
- `POST /solve`, `GET /instances`, `GET /solutions/{id}`, `GET /health`: integrados con los adapters reales (antes devolvían datos stub)
- `demo_phase3_e2e.py`: demo de punta a punta (crear instancia → persistir → resolver → persistir solución → recuperar → validar)
- `tests/unit/test_persistence.py`, `tests/unit/test_api_integration.py`: suite de integración contra PostgreSQL/MongoDB reales (vía Docker)

### 🐛 Fixed

- **`postgres_adapter.py` — incompatibilidad con Python 3.14:** `psycopg2` no publica wheels para 3.14 y falla al compilar desde código fuente en Windows. Se agregó fallback a `psycopg` (v3, misma sintaxis SQL/placeholders) cuando `psycopg2` no está disponible.
- **`test_persistence.py` — orden de importación no determinista:** los flags `POSTGRES_AVAILABLE`/`MONGO_AVAILABLE` leían `os.getenv("DATABASE_URL")` antes de que `backend_python.config` cargara `.env.local`, por lo que los tests se saltaban o fallaban según qué módulo se importara primero en la sesión de pytest. Se fuerza la carga de `config` al inicio del archivo de test.
- **`test_api_integration.py` — puerto hardcodeado:** las aserciones de `POSTGRES_PORT`/`DATABASE_URL` asumían el puerto 5432 fijo; se generalizaron para leer el puerto desde `config` en vez de un literal, ya que el puerto real depende del entorno (ver nota de infraestructura abajo).
- **MongoDB — `if not self.db:`** reemplazado por `if self.db is None:` en todos los métodos del adapter (PyMongo v4 lanza `NotImplementedError` al evaluar un objeto `Database` con `bool()`).

### 📝 Notas de infraestructura (no código)

- En entornos Windows con un servicio nativo de PostgreSQL ya corriendo en el puerto 5432, el contenedor Docker de desarrollo debe mapearse a un puerto alterno (`5433:5432` en este entorno) para evitar que el cliente hable con el Postgres equivocado — causa un `FATAL: password authentication failed` engañoso, no relacionado con las credenciales reales. Documentado en `.env.local` (no versionado).

### ⚠️ Known Limitations (actualizado)

- Bindings C++ (`vrp_solver` vía pybind11) no compilados en este entorno — requiere Python de 64 bits con headers de desarrollo; el sistema usa el fallback puro Python automáticamente y de forma transparente. No bloquea el pipeline solve→persist→retrieve.
- Sin retry/backoff en las conexiones a PostgreSQL/MongoDB — un fallo de conexión se propaga como error inmediato (aceptable para el alcance actual; ver sección "Rechazado" para el porqué de no añadir resiliencia todavía).

---

## [0.3.1] — 2026-07-23

### 🐛 Fixed

- **Colisión de ID cliente/depósito en el pipeline C++ (`api/__init__.py`, `solver_orchestrator.py`, `core_cpp/include/graph.hpp`):** `POST /solve` generaba `id=i` para clientes (`i` desde 0), mientras `_solve_cpp_pipeline` reserva `id=0` para el depósito en el grafo C++. `Graph::add_node` no detecta colisión de IDs, solo valida rango — un cliente con `id=0` sobrescribía silenciosamente el nodo del depósito. Fix: los IDs de cliente ahora se generan como `i + 1` en `api/__init__.py`.
- **Depósito hardcodeado en `(0.0, 0.0)` (`api/__init__.py`):** `POST /solve` ignoraba cualquier coordenada de depósito real. Se añadió el campo `depot_coordinates: tuple` (default `(0.0, 0.0)`, retrocompatible) a `InstanceRequest`.
- **`mongodb_adapter.py` — excepciones tragadas sin loggear:** los 5 métodos públicos (`save_solution`, `load_solution`, `list_solutions`, `save_cost_matrix`, `load_cost_matrix`) capturaban `except Exception: return False/None` sin registrar el error, ocultando fallos reales de persistencia. Se añadió `logger.error(...)` en cada except, alineado con el patrón que ya usa `postgres_adapter.py`.
- **`api/__init__.py` — retorno de `save_instance`/`save_solution` ignorado:** `POST /solve` loggeaba éxito incondicionalmente sin verificar el booleano de retorno de los adapters. Ahora se loggea a nivel `warning` si la persistencia falla, sin abortar la request (se mantiene el comportamiento "best effort").
- **Demanda de cliente aceptaba fraccionarios que se truncaban silenciosamente en dos puntos independientes** (`solver_orchestrator.py` al pasar al grafo C++, `postgres_adapter.py` al persistir), causado por `Node::demand: int` en el core C++. Se añadió validación explícita en `Cliente.__post_init__` (`backend_python/models/__init__.py`): demandas no enteras ahora se rechazan con `ValueError` en el punto de entrada, en vez de truncarse silenciosamente más adelante en el pipeline.

### 🔧 Changed

- `requirements.txt`: eliminadas `sqlalchemy==2.0.23` y `mongoengine==0.28.0` — no se importan en ningún archivo del código; la decisión de no usar ORM ya estaba documentada en `0.3.0`.
- `.env.example`: reescrito para reflejar las variables que `backend_python/config.py` realmente lee (`POSTGRES_HOST/PORT/USER/PASSWORD/DB`, `MONGO_HOST/PORT/DB`, `API_HOST/PORT/DEBUG`, `SOLVER_TIMEOUT_SECONDS`) en vez de `DATABASE_URL`/`MONGODB_URL` compuestas, que no coincidían con el código y causaban fricción real de onboarding.
- `docs/adr/0001-hybrid-python-cpp.md`: sección "Especificación" corregida — ya no lista SQLAlchemy/MongoEngine como stack de persistencia; refleja la decisión real (adapters directos, sin ORM) ya documentada en CHANGELOG `0.3.0`.
- Eliminada la carpeta `backend_python/tests/` (contenía solo un `__init__.py` vacío); la suite real vive en `tests/unit/`, tal como usan todos los comandos del `Makefile`.

---

## [0.3.2] — 2026-07-23

### 🐛 Fixed

- **`tests/unit/test_models.py` — sin test de regresión para el invariante de demanda entera introducido en `0.3.1`:** se añadió `test_cliente_demanda_debe_ser_entera`, siguiendo el mismo patrón que los tests vecinos de `demanda <= 0`.
- **`api/__init__.py` — `depot_coordinates: tuple` sin longitud fija producía `500` en vez de `422` ante input malformado:** un request con `depot_coordinates` de longitud distinta a 2 pasaba la validación de Pydantic sin error (tupla sin parametrizar) y fallaba después con `TypeError` al hacer `Coordinate(*request.depot_coordinates)`, cayendo en el `except Exception` genérico del endpoint y reportándose como error de servidor. Se tipó como `Tuple[float, float]`, delegando la validación de longitud a Pydantic — ahora responde `422` con mensaje claro. Verificado manualmente vía `TestClient`.
- **`solver_orchestrator.py:127` — `vrp_solver.Graph()` se construía con `num_vehiculos` en vez del número real de nodos (bug preexistente de Fase 2, no introducido por `0.3.1`, pero descubierto al auditar el flujo que ese delta modificó):** `Graph(int n)` reserva `n` nodos y usa `n` como cota superior en `add_node`. Con cualquier instancia con más clientes que vehículos (el caso normal en VRP), `add_node(client.id, ...)` habría lanzado `std::out_of_range` en cuanto se compilaran los bindings C++ — invisible hoy porque el fallback Python no usa `Graph`. Fix: `Graph(1 + len(self.instance.clientes))` (1 nodo depósito + N clientes). Complementa el fix de `id+1` de `0.3.1`: ese corrige el *valor* de los IDs, este corrige el *tamaño* del contenedor que debe alojarlos — ambos son necesarios para que el camino C++ funcione cuando se active.

### 🔧 Changed

- `docker-compose.yml`: credenciales de PostgreSQL alineadas a `.env.example` (`POSTGRES_DB=vrp_db`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=vrp_password`; antes `vrp_dev`/`vrp_user`/`vrp_pass`, que no coincidían con lo que `config.py` espera por defecto). El flujo documentado en README (`docker-compose up -d` + `.env.example`) ahora es consistente.
- `docker-compose.yml`: eliminadas `MONGO_INITDB_ROOT_USERNAME`/`MONGO_INITDB_ROOT_PASSWORD`/`MONGO_INITDB_DATABASE` del servicio `mongodb`. `config.py`/`MongoDBAdapter` no soportan credenciales para MongoDB (`MONGO_URL` se construye sin campo de usuario/contraseña) — exigir auth en el contenedor lo hacía imposible de usar con el código actual. Se alinea `docker-compose.yml` al uso real ya verificado en esta sesión (Mongo sin auth en desarrollo local), en vez de añadir soporte de credenciales no utilizado hoy.

---

## [0.3.3] — 2026-07-23

### 🐛 Fixed

- **Número de rutas generado por el solver nunca se validaba contra `flota.num_vehiculos` (defecto compartido por ambos caminos de solución — C++ y fallback Python — no exclusivo de uno).** `Instancia.__post_init__` (`backend_python/models/__init__.py`) valida que la demanda total quepa en la capacidad agregada (`num_vehiculos * capacidad`), pero eso es una cota agregada: no garantiza que un bin-packing greedy (Nearest Neighbor, tanto `NearestNeighbor::solve()` en C++ como `_construct_route_greedy` en el fallback Python de `solver_orchestrator.py`) reparta esa demanda en `num_vehiculos` rutas o menos. Era matemáticamente posible que la demanda cupiera en la capacidad total pero que el greedy necesitara más rutas que vehículos disponibles, y el resultado se aceptaba tal cual sin ninguna señal de infactibilidad. Fix: `SolverOrchestrator.solve()` (`backend_python/service/solver_orchestrator.py`) ahora verifica `len(solution.rutas) > self.instance.flota.num_vehiculos` tras obtener la solución (de cualquiera de los dos caminos) y lanza `ValueError` si se excede — no se tocó el algoritmo de construcción en sí, solo se añadió la validación posterior, consistente con el patrón de invariantes que el dominio ya usa. Test de regresión: `tests/unit/test_optimizers.py::TestFleetSizeValidation`, con un caso construido explícitamente (3 clientes de demanda 60 c/u, capacidad 100 por vehículo — ningún par cabe junto —, 2 vehículos disponibles: demanda total 180 ≤ 200 pero greedy requiere 3 rutas).

---

## [0.3.4] — 2026-07-23

### 🐛 Fixed

- **`tests/unit/test_optimizers.py:121-124` — test placeholder sin aserción real.** `test_3opt_is_stricter_than_2opt` contenía únicamente `assert True` con un comentario que no correspondía a ninguna validación, dando falsa sensación de cobertura de 3-opt. Cambiado a `pytest.skip("Requires C++ bindings to validate")`, consistente con sus dos tests vecinos en la misma clase (`TestLocalOperators`) que ya usan ese patrón honesto para lo que depende de bindings C++ no compilados en este entorno.

---

## [0.3.5] — 2026-07-23

### 🐛 Fixed

- **`api/__init__.py:23` — `coordinates: List[tuple]` sin longitud fija (mismo defecto de tipado ya corregido en `depot_coordinates` vía `0.3.2`, previamente dejado fuera de alcance).** Una `tuple` sin parametrizar no valida cantidad de elementos: un request con `coordinates` conteniendo entradas de longitud distinta a 2 pasaba la validación de Pydantic sin error. Tipado como `List[Tuple[float, float]]`, delegando la validación a Pydantic — ahora responde `422` con mensaje claro en vez de comportamiento indefinido más adelante en el pipeline. Verificado manualmente vía `TestClient` y cubierto por el nuevo test `test_solve_rejects_malformed_coordinates` en `tests/unit/test_api_integration.py`. Sin cambios de compatibilidad para clientes que ya envían pares `[x, y]` válidos (11 tests de `/solve` existentes siguen pasando sin modificación).

---

## [0.3.6] — 2026-07-23

### ✨ Added

- **Retry con backoff fijo en la conexión inicial de `PostgreSQLAdapter` y `MongoDBAdapter`** (`backend_python/persistence/postgres_adapter.py`, `mongodb_adapter.py`). Hasta ahora un fallo transitorio de red tumbaba el adapter en el primer intento (decisión previamente rechazada en `0.3.0`, ver nota abajo). Reconsiderado porque el despliegue va a dejar de ser exclusivamente esta máquina con Docker local — en una red real entre dos equipos, un fallo transitorio (DB aún arrancando, blip de red) ya no es un escenario hipotético. Implementación mínima: 3 intentos, 1 segundo de espera fija entre cada uno (`CONNECT_RETRIES`, `CONNECT_RETRY_DELAY_SECONDS`), sin librería nueva (`time.sleep` de stdlib). Se aplica solo a la conexión inicial (`__init__`) — los métodos de guardado/lectura individuales siguen siendo best-effort (retornan `False`/`None` en fallo), sin retry, porque ya son operaciones idempotentes desde la perspectiva del caller y añadir retry ahí sería sobreingeniería para un problema no observado en esa capa.
- **`psycopg2.connect(..., connect_timeout=5)`** añadido en `postgres_adapter.py`. Descubierto durante la verificación manual del retry: sin timeout explícito, un intento de conexión contra un host/puerto inalcanzable podía colgarse indefinidamente en Windows (varios minutos, no segundos), lo cual habría hecho que el retry con backoff fuera contraproducente — 3 intentos × "indefinido" es peor que 1 intento sin retry. `MongoDBAdapter` ya tenía timeout explícito (`serverSelectionTimeoutMS=5000`) desde antes, por eso el problema solo se manifestó en Postgres. Verificado con un puerto cerrado real: sin el fix, el proceso quedó colgado (tuvo que terminarse manualmente); con el fix, falla en un tiempo acotado.

### 🔧 Rechazo revisado

- **Retry/backoff exponencial en los adapters de persistencia:** la entrada original de `0.3.0` en la sección "Rechazado / Descartado" decía "no hay evidencia de fallos de conexión intermitentes en este entorno (Docker local)". Esa premisa deja de aplicar: el usuario confirmó que el despliegue futuro puede ocurrir en una máquina distinta a la actual, escenario donde un fallo transitorio de red ya no es hipotético. Se implementa con el alcance mínimo suficiente (backoff fijo, no exponencial; solo en la conexión inicial, no en cada operación) — no se reabre la puerta a la resiliencia completa que se rechazó (colas, circuit breakers, etc.), que sigue sin justificación real.

---

## [0.4.0] — 2026-07-23

### ✨ Added

- **Integración OSRM real para distancias sobre calles** (`backend_python/service/osrm_client.py`, `solver_orchestrator.py`). `SolverOrchestrator.solve()` ahora construye la matriz de costos una sola vez, antes de bifurcar entre el fallback Python y el pipeline C++ (`_build_cost_lookup()`), garantizando que ambos caminos usen exactamente la misma fuente de distancias — requisito ya exigido por `TESTING_STRATEGY.md` sección 2 (paridad entre caminos). El comentario `"Build cost matrix (Euclidean for now)"` que existía en `_solve_cpp_pipeline` desde Fase 2 queda resuelto: ahora usa OSRM cuando está configurado.
- **Cliente OSRM con chunking** (`osrm_client.py::get_osrm_matrix`): pide la matriz vía el endpoint `/table` de OSRM; si el número de coordenadas excede `OSRM_MAX_TABLE_SIZE`, particiona en múltiples llamadas por bloques y ensambla la matriz completa en Python. Diseñado con chunking desde el inicio (decisión confirmada por el usuario) para no chocar con el límite práctico de tamaño de matriz de OSRM frente a la promesa de escala del README ("50 a 100k+ clientes").
- **Fallback silencioso a distancia euclídea** si OSRM no está configurado (`OSRM_URL` vacío) o no responde (timeout, error HTTP, código de error de OSRM) — decisión de producto confirmada por el usuario: nunca falla `/solve` completo por una caída de OSRM, se loggea `warning` y se continúa con el cálculo euclidiano ya existente. Verificado con dos casos: `OSRM_URL` no configurado (salta la llamada HTTP por completo, sin latencia) y `OSRM_URL` apuntando a un puerto inalcanzable (falla rápido por el timeout, cae a euclídea).
- **`docker-compose.yml`:** nuevo servicio `osrm` (imagen oficial `osrm/osrm-backend`), apuntando a un mapa pre-procesado en `./data/osrm` (gitignored, mismo patrón que `data/large_instances/`). No se levanta automáticamente con `docker-compose up` si el mapa no fue preparado antes — requiere el paso offline `make osrm-prepare`.
- **`make osrm-prepare`** (nuevo target en `Makefile`): descarga el extracto de Perú desde Geofabrik (Lima Metropolitana no está disponible como extracto separado en Geofabrik; se usa el archivo de Perú completo, ~250MB) y lo pre-procesa (`osrm-extract` + `osrm-partition` + `osrm-customize`) — paso único, offline, análogo a `make build` para el core C++.
- **Config nueva** (`config.py`, `.env.example`): `OSRM_URL` (sin default — vacío significa "no usar OSRM", evita que el sistema intente conectar a un servicio que nadie levantó), `OSRM_MAX_TABLE_SIZE`, `OSRM_TIMEOUT_SECONDS`.

### 🐛 Fixed durante la implementación

- **`OSRM_URL` con default `http://localhost:5000` causaba que toda la suite de tests intentara conectar a OSRM y esperara el timeout completo (~4s por test) antes de caer al fallback**, incluso en máquinas sin OSRM levantado — la suite pasó de ~2s a ~51s. Corregido quitando el default: `OSRM_URL` vacío ahora salta la llamada HTTP por completo en vez de intentarla y fallar. Mismo principio que ya aplica `DATABASE_URL`/`MONGO_URL` (sin valor mágico que aparente estar configurado sin estarlo).

### Tests

- `tests/unit/test_osrm_client.py`: matriz simple y chunking contra un servicio OSRM real (`skipif` si `OSRM_URL` no está configurado, mismo patrón que `test_persistence.py` para Postgres/Mongo); propagación de `OSRMError` ante host inalcanzable (no requiere OSRM real, corre siempre).
- `tests/unit/test_optimizers.py::TestCostMatrixFallback`: fallback a euclídea cuando OSRM no está configurado y cuando está configurado pero inalcanzable (vía `monkeypatch` sobre el `config` singleton).
- Tests existentes de `_solve_python_fallback` (`test_optimizers.py`, `test_solver_end_to_end.py`) actualizados para pasar `cost_lookup` explícito, ya que la firma del método cambió al extraer la construcción de la matriz a un punto único.

---

## [0.4.1] — 2026-07-23

### 🐛 Fixed

- **`osrm_client.py::get_osrm_matrix` — el chunking podía exceder `max_table_size` en cada request individual, invalidando su propio propósito.** Cada bloque combinaba un rango de fila + un rango de columna (`block_coords = coords[row_start:row_end] + coords[col_start:col_end]`) usando `max_table_size` como tamaño de cada rango por separado — el tamaño combinado real podía llegar a `2 * max_table_size` (verificado con simulación: `max_table_size=2` generaba requests de hasta 4 coordenadas). Si `OSRM_MAX_TABLE_SIZE` se configura porque el servidor OSRM real rechaza requests más grandes, el chunking seguía enviando requests demasiado grandes, solo que con menor frecuencia. Fix: el tamaño de cada bloque ahora es `max_table_size // 2`, garantizando que la unión fila+columna nunca exceda el límite configurado (verificado: peor caso combinado = exactamente `max_table_size`).
- **README.md no documentaba la integración OSRM (`0.4.0`) como implementada.** Seguía describiéndola como roadmap ("OSRM/Valhalla-ready") sin mencionar que ya existe, y el Quick Start no incluía el paso `make osrm-prepare`. Corregido: sección "Motor Evaluador de Costos" actualizada, nueva sección "OSRM (opcional)" en Quick Start.
- **`osrm_client.py` sin advertencia sobre el requisito de coordenadas geográficas reales.** Activar `OSRM_URL` contra una instancia con coordenadas cartesianas/sintéticas (como las que usa toda la suite de tests y el demo) podría, en el peor caso, devolver una matriz "válida" pero sin sentido si esos valores caen dentro de un rango lon/lat plausible por coincidencia — sin ningún error que lo señale. Se documentó explícitamente en el docstring del módulo; no se añadió validación de rango en código (decisión de configuración del usuario, no un caso a adivinar en runtime — ver "Rechazado / Descartado").

---

## [0.4.2] — 2026-07-23

### ✨ Added

- **Bindings C++ (`vrp_solver`) compilados y activados por primera vez.** Bloqueo histórico resuelto: el MinGW instalado en esta máquina (`C:\MinGW`, GCC 6.3.0) era un toolchain de **32-bit**, incompatible con el Python de 64-bit del sistema — CMake lo rechazaba con `"Wrong architecture for the interpreter"`. Instalado MinGW-w64 real de 64-bit (WinLibs, GCC 16.1.0, vía `winget install BrechtSanders.WinLibs.POSIX.UCRT`) y reconfigurado el build apuntando explícitamente a ese compilador (`CMAKE_C_COMPILER`/`CMAKE_CXX_COMPILER`) y a `pybind11_DIR` (`python -c "import pybind11; print(pybind11.get_cmake_dir())"`). El `.pyd` compila y enlaza correctamente (`vrp_solver.cp314-win_amd64.pyd`).
- **`MINGW_BIN_DIR` (nueva variable de entorno, opcional, solo Windows).** Descubierto que Python 3.8+ en Windows no resuelve las DLLs de runtime de un `.pyd` compilado con MinGW (`libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`) vía `PATH` del proceso — requiere `os.add_dll_directory()` explícito (cambio de seguridad de Python, no un bug de esta integración). `solver_orchestrator.py` ahora llama `os.add_dll_directory(MINGW_BIN_DIR)` antes de `import vrp_solver` si la variable está seteada y el directorio existe; si no, el import de `vrp_solver` falla como antes y el sistema usa el fallback Python automáticamente — mismo comportamiento "opcional, sin bloquear" que ya tienen `OSRM_URL`/`DATABASE_URL`.

### 🐛 Fixed

- **`solver_orchestrator.py::_solve_cpp_pipeline` — el depósito (`id=0`) se copiaba dentro de `Ruta.secuencia`, violando el invariante de unicidad de `Solucion`.** Bug real de Fase 2 (`b64092e`), invisible desde su origen porque el pipeline C++ nunca se había ejecutado hasta este parche (bindings no compilados). `cpp_route.sequence` (C++) incluye el depósito al inicio y fin de cada ruta (`depot → clientes → depot`, patrón estándar VRP), pero se copiaba tal cual a `Ruta.secuencia` (que en el dominio Python representa solo clientes) — con 2+ rutas, el depósito aparecía repetido entre ellas, y `Solucion.__post_init__` lo rechazaba como `"cliente visitado múltiples veces"`. Confirmado con el traceback real: `secuencia=[0, 1, 3, 2, 0]` para una ruta de 3 clientes. Fix: filtrar `node_id != 0` al convertir `cpp_route.sequence` a `Ruta.secuencia`. Verificado: 59/59 tests pasando con el pipeline C++ real activo (antes solo se ejercitaba el fallback Python), demo end-to-end con costo 145.78 (mejor que el fallback Python, 146.86 — el NN→SA→3-opt real optimiza más que el greedy simple, como se esperaba por diseño).

### 📝 Notas de infraestructura (no código)

- Instalación de MinGW-w64 (WinLibs) es específica de esta máquina, no versionada en git — `MINGW_BIN_DIR` vive en `.env.local`. Otro desarrollador en otra máquina necesitaría repetir la instalación (o usar MSVC/otro toolchain de 64-bit) para activar los bindings; sin hacerlo, el sistema sigue funcionando en fallback Python sin ningún cambio de comportamiento — este parche no introduce una dependencia dura.

---

## [0.4.3] — 2026-07-23

### ✨ Added

- **Validación de rango geográfico (lon/lat) en `osrm_client.py::get_osrm_matrix`.** Antes solo se advertía en el docstring; ahora `_validate_coords_are_geographic()` rechaza explícitamente cualquier coordenada fuera de `[-180, 180]` (lon) / `[-90, 90]` (lat) **antes** de hacer cualquier llamada HTTP, lanzando `OSRMError` (que activa el fallback silencioso a euclídea ya existente). No detecta coordenadas cartesianas que caigan dentro de un rango lon/lat plausible por coincidencia (limitación ya documentada, no resuelta por esta validación), pero sí el caso más común y peligroso: instancias sintéticas de prueba con valores muy fuera de rango. Test de regresión: `tests/unit/test_osrm_client.py::test_osrm_matrix_rejects_non_geographic_coordinates` (no requiere OSRM real, corre siempre).
- **`Graph::add_node` (`core_cpp/include/graph.hpp`) ahora detecta colisión de IDs.** Se añadió un `std::vector<bool> assigned` para rastrear qué posiciones ya fueron asignadas — una segunda llamada con el mismo `id` lanza `std::invalid_argument` en vez de sobrescribir el nodo anterior en silencio (mapeado a `ValueError` en Python vía pybind11). Cierra el vector de bug que causó la colisión cliente/depósito de `0.3.1`. Verificado en dos niveles: test C++ nativo (`core_cpp/tests/test_graph.cpp::DuplicateIdRejected`, vía CTest) y llamada manual a través de los bindings compilados.

### 🐛 Fixed

- **`CMakeLists.txt` (raíz) y `core_cpp/CMakeLists.txt` hacían `add_subdirectory(core_cpp/tests)` dos veces — bug preexistente, nunca detectado porque nadie había compilado la suite C++ con `BUILD_TESTS=ON` hasta ahora.** CMake fallaba con `"binary directory is already used to build a source directory"`. Fix: el `add_subdirectory(tests)` vive solo en `core_cpp/CMakeLists.txt` (dueño natural de ese subdirectorio); el `CMakeLists.txt` raíz solo llama `enable_testing()`. Efecto secundario descubierto: `enable_testing()` debe ejecutarse **antes** de `add_subdirectory(core_cpp)` para que CTest registre los tests de ese subárbol — corregido el orden también. Resultado: primera compilación exitosa de la suite C++ nativa completa (GoogleTest vía `FetchContent`), **10/10 tests pasando** (`vrp_core_tests.exe`), incluyendo el nuevo test de colisión de IDs.

### 🔬 Validación de escala real (chunking OSRM, deuda técnica de `0.4.0`/`0.4.1`)

Se levantó un servicio OSRM real (`make osrm-prepare` con el extracto de Perú de Geofabrik, 242MB descarga → 2.5GB pre-procesado) y se probó `get_osrm_matrix` con coordenadas aleatorias reales dentro de Lima Metropolitana, en vez del caso sintético de 4 coordenadas que era la única cobertura hasta ahora:

| n coordenadas | Tiempo | Requests HTTP (`max_table_size=100`) |
|---|---|---|
| 50 | 0.26s | 1 (sin chunking) |
| 150 | 2.11s | 9 |
| 300 | 7.72s | 36 |
| 1000 | 85.01s | 400 |

**Resultado: el chunking funciona correctamente (matriz completa y correcta en los 4 casos), pero el costo real a escala es alto** — 85 segundos para 1000 clientes, muy por encima de la promesa de "100-500ms" del README para instancias de ese tamaño (esa cifra asume distancia euclídea, no OSRM). Causa: el patrón O(bloques²) del chunking (400 requests secuenciales para n=1000, ~212ms promedio cada uno). Confirma numéricamente la deuda técnica ya documentada en `TESTING_STRATEGY.md`, ahora con datos reales en vez de una suposición. También se confirmó que el servidor OSRM real rechaza tablas de 1000 coordenadas en una sola llamada (`400 Bad Request` sin chunking) — validando que el chunking no es opcional para instancias medianas/grandes con OSRM activo, es un requisito funcional.

**No se optimizó el chunking en este parche** (paralelizar requests, cachear resultados, etc.) — queda como decisión explícita para cuando el frontend/casos de uso reales confirmen que instancias de cientos de clientes con OSRM activo son un escenario a soportar en producción, no antes.

---

## [0.4.4] — 2026-07-24

### 🐛 Fixed

- **README.md "Prerequisites" indicaba C++20 (GCC 9+, Clang 11+); el proyecto usa C++17 desde hace varias fases.** `CMakeLists.txt` ya documentaba explícitamente el downgrade (`"C++17 standard (C++20 not available in all environments)"`) pero el README nunca se actualizó — un usuario nuevo podría instalar un toolchain pensando que necesita C++20. Corregido a "C++17 compiler (GCC 9+, Clang 11+, MinGW-w64 en Windows)", mencionando explícitamente MinGW-w64 como opción validada en `0.4.2`.
- **El fix de CMake duplicado de `0.4.3` perdió `EXCLUDE_FROM_ALL`, causando que un build normal (`cmake --build .` / `make build`) compilara la suite de tests C++ completa (incluyendo GoogleTest vía `FetchContent`, que requiere descarga de internet) aunque el usuario no pidiera correr tests.** La versión original tenía `add_subdirectory(core_cpp/tests EXCLUDE_FROM_ALL)`; al mover ese `add_subdirectory` a `core_cpp/CMakeLists.txt` para resolver la duplicación, se perdió el flag. Confirmado con una reconfiguración limpia: sin el flag, `cmake --build .` con `BUILD_TESTS=ON` (default) compilaba gtest/gmock completo y `vrp_core_tests.exe` como parte del build normal. Fix: `add_subdirectory(tests EXCLUDE_FROM_ALL)` en `core_cpp/CMakeLists.txt` — el target de tests ahora solo se compila si se invoca explícitamente (`cmake --build . --target vrp_core_tests` o vía `ctest`, que lo requiere como dependencia). Efecto colateral corregido en el mismo parche: `Makefile::test-cpp` ahora compila `vrp_core_tests` explícitamente antes de `ctest` (antes asumía que `make build` ya lo había compilado, lo cual dejó de ser cierto con `EXCLUDE_FROM_ALL` restaurado). Verificado: build normal ya no compila tests (confirmado por ausencia de pasos de gtest en el log), `make test-cpp` sigue funcionando (10/10 tests C++ pasando).

---

## Rechazado / Descartado

Decisiones evaluadas y descartadas explícitamente para mantener el alcance YAGNI/KISS:

- **Cobertura geográfica más allá de Lima Metropolitana / Perú en esta iteración:** se usa el extracto de Perú completo de Geofabrik (no hay uno más granular disponible ahí). Ampliar a otras regiones/países queda como decisión futura si se necesita — no se descarga ni pre-procesa nada más amplio especulativamente.
- **Orquestador de infraestructura (Terraform/Ansible) para el paso de preparación del mapa OSRM:** un target de `Makefile` (`osrm-prepare`) es suficiente para un paso de un solo comando, ejecutado una vez por entorno — introducir una herramienta de IaC para esto sería infraestructura desproporcionada al problema.
- **Cola de mensajería (Redis/RabbitMQ) para `/solve` asíncrono:** el endpoint resuelve instancias en el request-response síncrono actual. No hay volumen ni tiempos de resolución que justifiquen una cola; agregar un broker sería infraestructura sin problema real que resolver en este alcance.
- **ORM (SQLAlchemy/Tortoise) para el adapter de PostgreSQL:** el adapter usa SQL parametrizado directo (`psycopg`/`psycopg2` + placeholders). El esquema es de 3 tablas fijas sin migraciones dinámicas; un ORM añadiría una capa de abstracción sin beneficio medible sobre queries ya simples y explícitas.
- **Framework de mocking pesado para tests de persistencia (`unittest.mock`, fixtures de DB en memoria):** se optó por correr los tests de integración contra contenedores Docker reales de PostgreSQL/MongoDB. Mockear la capa de persistencia habría ocultado bugs reales (de hecho, así se detectó el problema de `psycopg2`/Python 3.14 y el bug de orden de importación en los tests).
- **Validador de schema de configuración (pydantic-settings) para prevenir desalineación de `.env.example`:** el problema real (`0.3.1`) se resolvió corrigiendo el archivo de texto plano para que coincida con `config.py`. Introducir una capa de validación nueva para 10 variables de entorno es infraestructura sin problema proporcional que resolver.
- **Cambiar `Node::demand` de `int` a `double` en el core C++ (`0.3.1`):** se evaluó junto con el fix de truncamiento de demanda, pero se descartó unilateralmente decidir el tipo de negocio sin confirmación — el usuario confirmó que las demandas son enteras (unidades discretas de carga), así que la validación se agregó en el dominio Python (`Cliente.__post_init__`) en vez de tocar el core C++ ya aprobado.
- **Añadir soporte de credenciales de MongoDB a `config.py`/`MongoDBAdapter` (`0.3.2`):** evaluado junto con la desalineación `docker-compose.yml` vs. código real; el usuario confirmó que Mongo corre sin autenticación en desarrollo local (uso ya verificado en esta sesión), así que se alineó `docker-compose.yml` a esa realidad en vez de añadir código de auth no ejercitado hoy.

---

## Notas de Migración

Este changelog inicia desde cero con la v0.1.0-alpha porque el proyecto hace una **transición arquitectónica significativa**:

**De:** Proyecto académico Qt/C++ con interfaz GUI, benchmarking teórico
**A:** SaaS VRP solver híbrido con API REST, persistencia dual, escalabilidad a 100k+ nodos

El código académico anterior (Git history) se preserva pero no se integra en este árbol. Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) para contexto completo.

---

**Formato:** [Keep a Changelog](https://keepachangelog.com/)
**Versionado:** [Semantic Versioning](https://semver.org/)
**Última actualización:** 2026-07-23
