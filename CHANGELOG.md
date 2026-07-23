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

## Notas de Migración

Este changelog inicia desde cero con la v0.1.0-alpha porque el proyecto hace una **transición arquitectónica significativa**:

**De:** Proyecto académico Qt/C++ con interfaz GUI, benchmarking teórico
**A:** SaaS VRP solver híbrido con API REST, persistencia dual, escalabilidad a 100k+ nodos

El código académico anterior (Git history) se preserva pero no se integra en este árbol. Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) para contexto completo.

---

**Formato:** [Keep a Changelog](https://keepachangelog.com/)
**Versionado:** [Semantic Versioning](https://semver.org/)
**Última actualización:** 2026-07-23
