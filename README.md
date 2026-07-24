# [PROYECTO LIBRE] VRP Solver — Optimización del Problema de Ruteamiento de Vehículos

**Migración a Producción: Arquitectura Híbrida Python/C++ con Orquestación Inteligente**

**Equipo:** Grupo de 3 integrantes | **Docente:** GUERRA GRADOS, Luis Angel  
**Institución:** EP: Ciencia de la Computación — UNMSM  
**Fase:** Proyecto Final Académico (Completado) → **Escalado a Producción (Vigente)**

---

## 📖 Descripción

Solver de **Problema de Ruteamiento de Vehículos (VRP)** que evolucionó de una solución académica en Qt/C++17 a una **arquitectura híbrida Python/C++** orientada a producción.

Resuelve instancias complejas mediante orquestación inteligente de múltiples heurísticas:
- **Motor de Construcción Inicial:** Generación modular de semillas concurrentes (inspirado en VeRyPy)
- **Motor de Optimización:** Simulated Annealing con calibración dinámica vía DRL (inspirado en pytorch-drl4vrp)
- **Motor Evaluador de Costos:** Matrices de adyacencia dirigidas en C++ (inspirado en Vroom)
- **Operador de Pulido:** Búsqueda local 3-opt LKH-inspired para refinamiento intra-ruta

**Propósito:** Proporcionar un solver versátil que escale de 50 a 100k+ clientes, manteniendo trazabilidad académica y producción-grade en deployments.

---

## 🏗️ Arquitectura (Hybrid Python/C++)

```
vrp_project/
├── backend_python/           # Orquestador, dominio, API REST
│   ├── api/                  # FastAPI endpoints
│   ├── models/               # Entidades (Instancia, Cliente, Solución, Ruta)
│   ├── persistence/          # Adapters (MongoDB, PostgreSQL)
│   ├── service/              # Orquestación (solver_orchestrator, validation)
│   └── tests/                # Suite TDD (unit + integration)
│
├── core_cpp/                 # Núcleo algorítmico de alto rendimiento
│   ├── include/
│   │   ├── graph.hpp         # Estructura de grafo dirigido
│   │   ├── cost_matrix.hpp   # Matriz de adyacencia asimétrica
│   │   ├── builders/         # Heurísticas de construcción
│   │   ├── optimizers/       # Motores de optimización (SA, ILS)
│   │   ├── operators/        # Operadores locales (2-opt, 3-opt, Ruin-Recreate)
│   │   ├── solution.hpp      # Estructura de solución
│   │   └── bindings.hpp      # Interface pybind11
│   ├── src/                  # Implementaciones .cpp
│   └── tests/                # Tests unitarios C++
│
├── tests/                    # Suite integrada (Python + C++)
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│       ├── instances.json
│       ├── benchmarks/
│       │   ├── small_instances.json    # <100 nodos
│       │   ├── medium_instances.json   # 100-1k nodos
│       │   └── large_instances.json    # >1k nodos
│
├── docs/
│   ├── README.md             # Este archivo
│   ├── ARCHITECTURE.md       # Diseño técnico en detalle
│   ├── API.md               # Especificación REST
│   ├── CREDITS.md           # Atribuciones a fuentes académicas
│   ├── adr/                 # Architecture Decision Records
│   │   ├── 0001-hybrid-python-cpp.md
│   │   ├── 0002-asymmetric-cost-matrices.md
│   │   ├── 0003-drl-parameter-calibration.md
│   │   └── 0004-ruin-recreate-operators.md
│   └── references.md        # Repos inspiradores con mapeo de ideas
│
├── requirements.txt         # Dependencias Python + build tools
├── CMakeLists.txt          # Build C++ + integración pybind11
├── Makefile                # Helpers: make build, make test, make run
├── docker-compose.yml      # Dev environment (PostgreSQL, MongoDB)
├── .env.example            # Configuración de ejemplo
├── CHANGELOG.md            # Historia de cambios (migración)
└── .gitignore
```

### Principios de Diseño

- **YAGNI:** Sin abstracciones especulativas. Cada componente existe porque es necesario.
- **Inmutabilidad:** Datos entre Python↔C++ se pasan como estructuras inmutables (zero-copy via numpy).
- **Trazabilidad:** Cada decisión arquitectónica está documentada en ADRs con referencias explícitas a fuentes académicas.
- **TDD:** Tests validan tanto orquestación Python como rendimiento C++.

---

## 🎯 Características Principales

### Motor de Construcción Inicial
- Generación modular de múltiples semillas concurrentes (VeRyPy-inspired)
- Estrategias: Nearest Neighbor, Farthest, Random, Regret-based
- Lanzamiento paralelo en Python con recolección de mejores soluciones

### Motor de Optimización
- **Simulated Annealing** clásico + calibración dinámica de temperatura vía DRL (pytorch-drl4vrp-inspired)
- Operadores de movimiento: 2-opt intra-ruta, Or-opt
- Fallback a Ruin-Recreate (jsprit-inspired) si estancamiento

### Motor Evaluador de Costos
- Matrices de adyacencia **dirigidas** (no asume simetría euclidiana)
- Cálculo en C++ con pybind11 binding (zero-copy numpy arrays)
- Distancia euclidiana por defecto; **integración OSRM implementada** para distancias reales sobre calles (`OSRM_URL` en `.env.local`, ver Quick Start) — fallback automático a euclídea si OSRM no está configurado o no responde. Requiere coordenadas geográficas reales (lon, lat); Valhalla queda como alternativa futura, no implementada.

### Operador de Pulido Final
- 3-opt LKH-inspired para refinamiento intra-ruta post-optimización
- Garantía de no-deterioro: solo acepta movimientos que mejoran

### API REST
- `POST /solve` — Resuelve una instancia (async)
- `GET /solve/{job_id}` — Obtiene resultado
- `POST /validate` — Valida invariantes de solución
- `GET /instances` — Lista instancias persistidas

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ (64-bit)
- C++17 compiler (GCC 9+, Clang 11+, MinGW-w64 en Windows)
- CMake 3.20+
- Docker (opcional, para dev env)

### Build & Run

```bash
# Setup
python -m venv venv
source venv/bin/activate  # o venv\Scripts\activate en Windows
pip install -r requirements.txt

# Build C++ core
make build

# Run tests
make test

# Start API server
make run
# API disponible en http://localhost:8000
```

### Dev Environment (Docker)

```bash
docker-compose up -d
# PostgreSQL + MongoDB listos en localhost
make build && make test
```

### OSRM (opcional — distancias reales sobre calles)

```bash
make osrm-prepare   # descarga + pre-procesa el mapa (una sola vez, offline, ~250MB)
docker-compose up -d osrm
# Configurar OSRM_URL=http://localhost:5000 en .env.local
```

Sin este paso, el solver usa distancia euclídea automáticamente (comportamiento por defecto, sin configuración adicional).

---

## 📊 Rendimiento Esperado

| Tamaño Instancia | Nodos | Tiempo Solve | Hardware |
|---|---|---|---|
| Pequeña | <100 | 10-50ms | CPU (cualquiera) |
| Mediana | 100-1k | 100-500ms | CPU moderno |
| Grande | 1k-10k | 1-5s | CPU moderno + 8GB RAM |

---

## 📚 Documentación

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Diseño técnico profundo
- **[API.md](docs/API.md)** — Especificación REST con ejemplos
- **[CREDITS.md](docs/CREDITS.md)** — Tabla de atribuciones académicas
- **[ADRs](docs/adr/)** — Decisiones arquitectónicas justificadas
- **[references.md](docs/references.md)** — Mapeo repos → ideas aplicadas

---

## 🎓 Créditos y Referencias Académicas

Este proyecto integra investigación e implementaciones de código abierto reconocidas:

| Fuente | Contribución | URL |
|--------|--------------|-----|
| **Vroom** | Matrices de costo dirigidas y evaluación asincrónica | https://github.com/VROOM-Project/vroom |
| **LKH** | Búsqueda local de alto rendimiento (3-opt) | http://www.akira.ruc.dk/~keld/research/LKH/ |
| **VeRyPy** | Generación modular de heurísticas semilla | https://github.com/tpvasconcelos/routetools |
| **PyVRP** | Arquitectura híbrida Python/C++ y bindings pybind11 | https://github.com/PyVRP/PyVRP |
| **pytorch-drl4vrp** | Calibración dinámica de parámetros vía Deep RL | https://github.com/yd-kwon/pytorch-drl4vrp |
| **jsprit** | Paradigma destructivo/constructivo (Ruin-Recreate) | https://github.com/graphhopper/jsprit |
| **timefold-quickstarts** | Aislamiento y validación de invariantes | https://github.com/TimefoldAI/timefold-quickstarts |
| **Rosomaxa (vrp)** | Gestión de memoria inmutable y zero-copy | https://github.com/reinterpretcat/vrp |
| **Open-VRP** | Filosofía TDD en heurísticas | https://github.com/openvrp/open-vrp |
| **VRP-RL** | Pre-clasificación de instancias vía clustering | https://github.com/OptMLGroup/VRP-RL |

Ver [CREDITS.md](docs/CREDITS.md) para detalles de cada contribución.

---

## 📄 Licencia

Este proyecto es de **uso libre** bajo licencia [MIT/Apache 2.0 — pendiente de definir].

---

## 👥 Autores

- **Grupo de 3 integrantes** — Desarrollo y arquitectura
- **Docente:** GUERRA GRADOS, Luis Angel — Supervisión académica
- **Comunidad Open Source** — Referencias y benchmarking

---

## 🔗 Enlaces Útiles

- [Especificación VRP Clásica](https://en.wikipedia.org/wiki/Vehicle_routing_problem)
- [CVRPLIB — Benchmark Estándar](http://vrp.atd-lab.inf.puc-rio.br/)
- [OR-Tools de Google](https://developers.google.com/optimization)

---

**Última actualización:** 2026-07-23  
**Versión:** 0.1.0-alpha (Migración en progreso)
