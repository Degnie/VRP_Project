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

## Rechazado / Descartado

Decisiones evaluadas y descartadas explícitamente para mantener el alcance YAGNI/KISS:

- **Cola de mensajería (Redis/RabbitMQ) para `/solve` asíncrono:** el endpoint resuelve instancias en el request-response síncrono actual. No hay volumen ni tiempos de resolución que justifiquen una cola; agregar un broker sería infraestructura sin problema real que resolver en este alcance.
- **ORM (SQLAlchemy/Tortoise) para el adapter de PostgreSQL:** el adapter usa SQL parametrizado directo (`psycopg`/`psycopg2` + placeholders). El esquema es de 3 tablas fijas sin migraciones dinámicas; un ORM añadiría una capa de abstracción sin beneficio medible sobre queries ya simples y explícitas.
- **Retry/backoff exponencial en los adapters de persistencia:** documentado como pendiente en el estado de Fase 3, pero no implementado ahora — no hay evidencia de fallos de conexión intermitentes en este entorno (Docker local); añadir resiliencia para un fallo no observado es sobreingeniería prematura.
- **Framework de mocking pesado para tests de persistencia (`unittest.mock`, fixtures de DB en memoria):** se optó por correr los tests de integración contra contenedores Docker reales de PostgreSQL/MongoDB. Mockear la capa de persistencia habría ocultado bugs reales (de hecho, así se detectó el problema de `psycopg2`/Python 3.14 y el bug de orden de importación en los tests).
- **Validador de schema de configuración (pydantic-settings) para prevenir desalineación de `.env.example`:** el problema real (`0.3.1`) se resolvió corrigiendo el archivo de texto plano para que coincida con `config.py`. Introducir una capa de validación nueva para 10 variables de entorno es infraestructura sin problema proporcional que resolver.
- **Cambiar `Node::demand` de `int` a `double` en el core C++ (`0.3.1`):** se evaluó junto con el fix de truncamiento de demanda, pero se descartó unilateralmente decidir el tipo de negocio sin confirmación — el usuario confirmó que las demandas son enteras (unidades discretas de carga), así que la validación se agregó en el dominio Python (`Cliente.__post_init__`) en vez de tocar el core C++ ya aprobado.

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
