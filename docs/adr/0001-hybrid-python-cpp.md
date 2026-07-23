# ADR-0001: Arquitectura Híbrida Python/C++ para Escalabilidad de Producción

**Fecha:** 2026-07-23  
**Estado:** Aceptado  
**Autores:** Grupo de Investigación VRP UNMSM

---

## Problema

El proyecto académico original fue implementado en **Qt/C++17 monolítico**, lo que permitió:
- ✅ Interfaz gráfica responsiva
- ✅ Análisis teórico riguroso de complejidad
- ✅ Presentación académica exitosa

Sin embargo, al escalar a **producción real**, este monolito presenta limitaciones:

1. **Tiempo de iteración lento:** Cambios en lógica de negocio requieren recompile de toda la aplicación
2. **Acoplamiento dominio-algoritmo:** Modelos de dato mezclados con C++ raw; difícil mantener invariantes
3. **Escalabilidad limitada:** GUI bloquea solver; concurrencia compleja
4. **Testing oneroso:** Tests GUI requieren simulación de eventos; cobertura baja
5. **Deployment monolítico:** No hay separación clara entre core + API

---

## Decisión

Adoptar **arquitectura híbrida Python/C++** similar al patrón de **PyVRP**:

```
┌─────────────────────────────────────────────────┐
│     Backend Python (FastAPI)                    │
│  ┌──────────────────────────────────────────┐   │
│  │  API Layer (HTTP)                        │   │
│  ├──────────────────────────────────────────┤   │
│  │  Orquestador (solver_orchestrator.py)    │   │
│  │  - Valida invariantes                    │   │
│  │  - Maneja persistencia                   │   │
│  │  - Secuencia de construcción→optimización│  │
│  ├──────────────────────────────────────────┤   │
│  │  Modelos de Dominio (models/)            │   │
│  │  - Instancia, Cliente, Solución, Ruta   │   │
│  └──────────────────────────────────────────┘   │
│           │                                      │
│           │ pybind11 bindings (zero-copy)       │
│           ↓                                      │
└─────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────┐
│     Core C++ (CMake build)                      │
│  ┌──────────────────────────────────────────┐   │
│  │  Algoritmos (100% velocidad)             │   │
│  │  - Graph, CostMatrix (dirigido)          │   │
│  │  - Builders (Greedy, Farthest, etc)     │   │
│  │  - Optimizers (SA, ILS, Ruin-Recreate)  │   │
│  │  - Operators (2-opt, 3-opt, Or-opt)     │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### Especificación

**Backend Python:**
- Framework: **FastAPI** (REST API ligero y rápido)
- ORM: **SQLAlchemy** (PostgreSQL) + **MongoEngine** (MongoDB)
- Testing: **pytest** + fixtures
- Validación: **Pydantic** para models
- Concurrencia: Python async/await (construcción multisemilla)

**Core C++:**
- Standard: **C++20** (std::concepts, std::jthread)
- Build: **CMake 3.20+**
- Bindings: **pybind11** (zero-copy numpy arrays)
- Testing: **Google Test (gtest)**

**Data Flow:**
```
Python: Instancia(clientes, capacidad)
   ↓ (numpy array de coordenadas + demandas)
C++: solve(coords, demands, capacity) → Solution(rutas, costo)
   ↓ (numpy array de secuencias de clientes)
Python: Solución(rutas) + persistencia
```

---

## Justificación

### 1. Separación de Responsabilidades

**Python maneja negocio:** validación, persistencia, API contracts  
→ Fácil cambiar reglas sin recompilar

**C++ maneja matemática pura:** evaluación, optimización, cálculos  
→ Máximo rendimiento donde importa

### 2. Precedente en Producción

**PyVRP** (https://github.com/PyVRP/PyVRP) implementa exactamente este patrón:
- Backend Python + C++20 core
- pybind11 bindings
- Usado en enterprise VRP solving
- Mantenido activamente (2024+)

**Evidencia:** PyVRP escala a 10k+ clientes con latency aceptable.

### 3. Velocidad de Iteración

**Python:** Tests rápidos, sin compilación, REPL friendly
```python
# Cambiar lógica de construcción en segundos
from backend_python.builders import NewBuilder
def test_new_builder():
    instance = load_fixture("small_instances.json")
    builder = NewBuilder()
    solution = builder.solve(instance)
    assert solution.is_valid()
```

**C++:** Compilación única, deployment como .so binario

### 4. Testing en Dos Capas

**Capa Python:** Tests de orquestación, validación, persistencia (rápido, sin recompile)
```bash
pytest tests/unit/test_orchestrator.py  # <1s
```

**Capa C++:** Tests de algoritmos, rendimiento, edge cases (riguroso)
```bash
ctest --output-on-failure  # benchmark suite
```

### 5. Escalabilidad Horizontal

- **Orquestador Python** → Stateless, easy to replicate en Kubernetes
- **Core C++** → Compilado una vez, compartido entre instancias
- **Persistencia** → PostgreSQL + MongoDB separados (no en binario)

---

## Impacto de Alternativas Rechazadas

### ❌ Opción 1: Monolito Python Puro (YAGNI)
**Ventaja:** Desarrollo rápido  
**Desventaja:** GIL limita paralelismo de evaluación de costos; escalabilidad a 10k+ nodos sufre

**Descartado porque:** Benchmark de Vroom/PyVRP muestra que C++ gana 20-50x en cálculos puros.

### ❌ Opción 2: Monolito C++ Puro
**Ventaja:** Máxima velocidad  
**Desventaja:** Iteración lenta, testing engorroso, imposible API REST sin framework pesado

**Descartado porque:** Vuelve imposible escalar el equipo; cada cambio de negocio → full rebuild.

### ❌ Opción 3: Microservicios Complejos (Overkill)
**Ventaja:** Escalabilidad máxima (teórica)  
**Desventaja:** YAGNI; overhead de IPC, latency entre servicios

**Descartado porque:** MVP no justifica complejidad; hybrid es más simple y suficiente.

---

## Riesgos Mitigados

| Riesgo | Mitigación |
|--------|-----------|
| **Impedancia Python↔C++** | pybind11 maneja serialización; numpy es standard |
| **GIL en Python** | Construcción (CPU-light) en Python; evaluación (CPU-heavy) en C++ |
| **Build complexity** | CMakeLists.txt centralizado; Makefile helpers |
| **Debugging hybrid** | Separar tests: pytest para Python, gtest para C++ |
| **Versioning bindings** | Pinear pybind11 en requirements.txt |

---

## Cambios Estructurales Requeridos

### En este ADR:

1. ✅ Crear `/backend_python` con estructura dominio-centric
2. ✅ Crear `/core_cpp` con algoritmos modularizados
3. ✅ Definir interface pybind11 (`bindings.cpp`)
4. ✅ TDD en ambas capas (pytest + gtest)
5. ✅ CMakeLists.txt + Makefile + docker-compose para dev

### En ADRs futuros:

- ADR-0002: Matrices asimétricas (cost_matrix.hpp)
- ADR-0003: Calibración DRL de parámetros SA
- ADR-0004: Operadores Ruin-Recreate modulares

---

## Referencia Bibliográfica

**PyVRP: Hybrid Architecture for VRP Solving**
- https://github.com/PyVRP/PyVRP
- Fecha: 2023-2026 (vigente)
- Pattern: Python orchestrator + C++20 backend
- Status: Production-ready

**pybind11: Seamless Operability Between C++11 and Python**
- https://pybind11.readthedocs.io/
- Ref: Simplifies zero-copy numpy integration

**Vroom: Ultra-fast, Production-ready VRP Solver**
- https://github.com/VROOM-Project/vroom
- Ref: Validación de que arquitectura C++ puro es viable pero requiere API wrapper

---

## Consecuencias

### Positivas ✅

1. **Mantenibilidad:** Dominio en Python → cambios rápidos sin recompile
2. **Performance:** C++ core → sub-100ms solves para instancias medianas
3. **Testing:** Ambas capas testeable independientemente
4. **Deployment:** Docker-izable; Kubernetes-friendly
5. **Talento:** Más fácil reclutar devs Python que full C++

### Negativas ⚠️

1. **Curva aprendizaje:** Team necesita entender C++ + pybind11 basics
2. **Build tools:** Requiere C++ compiler + CMake (pero viene con venv setup)
3. **Debugging:** Stacktraces Python↔C++ más complejos
4. **Latency IPC:** Overhead pybind11 (~1-2ms por call; aceptable)

### Neutral ◇

1. **Duplicación de tipos:** Algunos tipos existen en C++ y Python (mitigado con shared_types.hpp)
2. **Testing end-to-end:** Requiere fixtures compartidas

---

## Aprobación

- **Propuesto por:** Grupo de Investigación VRP UNMSM
- **Revisado por:** (Pendiente)
- **Aprobado por:** (Pendiente)

---

## Seguimiento

- [ ] Implementar estructura de directorios
- [ ] Crear CMakeLists.txt base
- [ ] Implementar bindings.cpp (pybind11)
- [ ] Tests unitarios Python
- [ ] Tests unitarios C++
- [ ] Integración CI/CD (GitHub Actions)

---

**Versión:** 1.0  
**Última actualización:** 2026-07-23
