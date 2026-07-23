# Créditos y Referencias Académicas

Este proyecto está construido sobre investigación, implementaciones de código abierto y patrones validados en producción de múltiples fuentes académicas e industriales. Esta documento proporciona atribución explícita a cada contribución.

---

## Referencias Técnicas Integradas

### 1. **Vroom** — Matriz de Costo Dirigida
**URL:** https://github.com/VROOM-Project/vroom  
**Licencia:** AGPL-3.0

**Contribución:**
- Cálculos espaciales asincrónica y matrices de adyacencia dirigidas en C++
- Eliminación de la suposición de simetría euclidiana
- Evaluación de costos en milisegundos

**Cómo se aplica en nuestro proyecto:**
- `core_cpp/include/cost_matrix.hpp` — Implementación de matriz asimétrica
- Motor Evaluador de Costos permite distancias asimétricas (A→B ≠ B→A)
- Soporte para matrices pre-computadas y cálculo dinámico

**Papel Académico:** Vroom Project [Ver referencias]

---

### 2. **LKH** — Búsqueda Local de Alto Rendimiento
**URL:** http://www.akira.ruc.dk/~keld/research/LKH/  
**Licencia:** Freeware (no open-source)

**Contribución:**
- Rigurosidad matemática en búsqueda local
- Algoritmo k-opt eficiente (especialmente 3-opt)
- Estrategias de restart y perturbación

**Cómo se aplica en nuestro proyecto:**
- `core_cpp/include/operators/lkh_inspired.hpp` — 3-opt LKH-inspired
- Subrutina final de "pulido" post-SA para refinamiento intra-ruta
- Garantía de no-deterioro (solo movimientos mejoradores)

**Importancia:** LKH es el benchmark de oro en VRP local search; nuestro 3-opt está inspirado en su rigor.

---

### 3. **VeRyPy** — Generación Modular de Heurísticas
**URL:** https://github.com/tpvasconcelos/routetools  
**Licencia:** MIT

**Contribución:**
- Generación modular de múltiples heurísticas semilla
- Estrategias: Nearest Neighbor, Farthest, Regret-k, Random

**Cómo se aplica en nuestro proyecto:**
- `backend_python/service/` — Motor de Construcción Inicial multisemilla
- Lanzamiento concurrente de N heurísticas iniciales
- Recolección del mejor resultado para alimentar optimización

**Ejemplo:**
```python
# Inspirado en VeRyPy, generamos múltiples semillas
builders = [NearestNeighbor(), FarthestInsertion(), RandomInsertion()]
initial_solutions = [b.build(instance) for b in builders]
best_initial = min(initial_solutions, key=lambda s: s.cost)
```

---

### 4. **PyVRP** — Arquitectura Híbrida Python/C++
**URL:** https://github.com/PyVRP/PyVRP  
**Licencia:** MIT

**Contribución:**
- Patrón de arquitectura Python (orquestador) + C++ (core)
- pybind11 bindings para integración zero-copy
- Separación clara: dominio (Python) vs. algoritmos (C++)

**Cómo se aplica en nuestro proyecto:**
- Estructura `/backend_python` (dominio) ↔ `/core_cpp` (algoritmos)
- `core_cpp/src/bindings.cpp` — Exposición de C++ a Python vía pybind11
- Modelos de dato compartidos sin serialización

**Impacto:** Este patrón permite iterar dominio rápidamente sin recompilar C++.

---

### 5. **pytorch-drl4vrp** — Calibración Dinámica de Parámetros
**URL:** https://github.com/yd-kwon/pytorch-drl4vrp  
**Licencia:** MIT

**Contribución:**
- Ajuste dinámico de parámetros heurísticos vía Deep Reinforcement Learning
- Aprendizaje de política para calibración de temperatura en SA
- Capacidad de adaptación a características de instancia

**Cómo se aplica en nuestro proyecto:**
- `core_cpp/optimizers/simulated_annealing.hpp` — SA con parámetros dinámicos
- Temperatura inicial, factor de enfriamiento y max-iterations calibrados vía DRL
- Control adaptativo: la política aprende qué parámetros funcionan mejor por tipo de instancia

**Nota:** Integración completa de DRL está en roadmap (v0.2+); v0.1 tiene skeleton.

---

### 6. **jsprit** — Operador Ruin-Recreate
**URL:** https://github.com/graphhopper/jsprit  
**Licencia:** Apache 2.0

**Contribución:**
- Paradigma destructivo/constructivo (Ruin-Recreate)
- Operadores modulares: radial, random, worst-jobs, cluster-based
- Arquitectura extensible para nuevos operadores

**Cómo se aplica en nuestro proyecto:**
- `core_cpp/include/operators/` — Estructura modular de operadores
- Fallback a Ruin-Recreate si SA se estanca en óptimo local
- Separación builders/, optimizers/, operators/ permite agregar 10+ variantes sin refactor

---

### 7. **timefold-quickstarts** — Aislamiento de Invariantes
**URL:** https://github.com/TimefoldAI/timefold-quickstarts  
**Licencia:** Apache 2.0

**Contribución:**
- Separación explícita de reglas estáticas (constraints) vs. heurísticas
- Validación de invariantes en layer dedicada
- Pensamiento declarativo: qué debe cumplirse, no cómo

**Cómo se aplica en nuestro proyecto:**
- `backend_python/models/invariantes.py` — Clase Invariantes
- Validación centralizada: capacidad, unicidad, ciclos cerrados
- Separation of concerns: orquestador valida invariantes antes/después de C++

**Ventaja:** Facilita agregar nuevas restricciones sin modificar solver core.

---

### 8. **Rosomaxa (vrp)** — Gestión de Memoria Inmutable
**URL:** https://github.com/reinterpretcat/vrp  
**Licencia:** Apache 2.0

**Contribución:**
- Diseño de flujo de datos inmutable
- Zero-copy passing de estructuras entre capas
- Garantía de integridad en paso Python↔C++

**Cómo se aplica en nuestro proyecto:**
- `core_cpp/include/shared_types.hpp` — Tipos header-only compartidos
- Numpy arrays pasados a C++ sin copia (memoria compartida)
- Soluciones como estructuras immutables (no se modifican, se crean nuevas)

**Implicación:** Código más predecible y menos bugs por aliasing/mutations.

---

### 9. **Open-VRP** — Filosofía TDD en Heurísticas
**URL:** https://github.com/openvrp/open-vrp  
**Licencia:** MIT

**Contribución:**
- Test-Driven Development aplicado a solvers heurísticos
- Inmutabilidad como propiedad testeable
- Suite de tests unificada (unit + integration)

**Cómo se aplica en nuestro proyecto:**
- `tests/unit/` y `tests/integration/` — Suite TDD
- Tests Python validan orquestador
- Tests C++ validan algoritmos individuales
- Fixtures estratificadas por tamaño de instancia

**Filosofía:** "If it's not tested, it's broken."

---

### 10. **VRP-RL** — Pre-clasificación de Instancias
**URL:** https://github.com/OptMLGroup/VRP-RL  
**Licencia:** MIT

**Contribución:**
- Análisis de características de instancia (dispersión, densidad)
- Selección de heurística inicial basada en clustering
- Predicción de dificultad relativa

**Cómo se aplica en nuestro proyecto:**
- `backend_python/service/instance_classifier.py` — Pre-clasificación opcional
- Análisis de dispersión de clientes antes de invocar C++
- Routing a diferentes builders según características detectadas

**Ejemplo:**
```python
# Si instancia es "clustered" → usar FarthestInsertion
# Si instancia es "dispersada" → usar Regret-based
dispersión = calculate_dispersion(instance.clients)
builder = FarthestInsertion() if dispersión > THRESHOLD else RegretInsertion()
```

---

## Tabla Resumen: Idea → Aplicación

| Fuente | Idea Clave | Módulo en Proyecto | Tipo |
|--------|-----------|-------------------|------|
| Vroom | Matrices asimétricas en C++ | `core_cpp/cost_matrix.hpp` | Algoritmo |
| LKH | 3-opt riguroso | `core_cpp/operators/lkh_inspired.hpp` | Algoritmo |
| VeRyPy | Construcción multisemilla | `backend_python/builders/` | Diseño |
| PyVRP | Python/C++ + pybind11 | Toda la arquitectura | Arquitectura |
| pytorch-drl4vrp | DRL calibration | `core_cpp/simulated_annealing.hpp` | Parámetros |
| jsprit | Ruin-Recreate modular | `core_cpp/operators/` | Diseño |
| timefold | Aislamiento invariantes | `backend_python/invariantes.py` | Validación |
| Rosomaxa | Immutable data flow | `core_cpp/shared_types.hpp` | Diseño |
| Open-VRP | TDD philosophy | `tests/` | Práctica |
| VRP-RL | Pre-clasificación | `backend_python/instance_classifier.py` | Heurística |

---

## Licencias Respectadas

- **AGPL-3.0** (Vroom) — Cumplida: nuestro core_cpp no redistribuye Vroom binariamente
- **MIT** (VeRyPy, PyVRP, VRP-RL, Open-VRP) — Compatible; proyecto usa MIT
- **Apache 2.0** (jsprit, timefold, Rosomaxa) — Compatible; proyecto usa Apache 2.0 / MIT dual
- **Freeware** (LKH) — Solo inspiración de algoritmo, no código copiado

---

## Cómo Citar Este Proyecto

Si utilizas este solver en investigación, favor citar:

```bibtex
@software{vrp_solver_2026,
  title={VRP Solver — Hybrid Python/C++ Production Architecture},
  author={Grupo de Investigación, UNMSM},
  year={2026},
  url={https://github.com/usuario/vrp_solver},
  note={Built on ideas from Vroom, PyVRP, LKH, VeRyPy, jsprit, and others}
}
```

---

## Contribuciones Futuras

Si deseas contribuir:

1. Respeta la estructura modular existente
2. Agrega nuevas ideas siempre con ADR explicativo
3. Atribuye explícitamente si basas en código externo
4. Mantén este documento actualizado

---

**Última actualización:** 2026-07-23  
**Mantiene actualizado con:** Cambios en CHANGELOG.md y nuevos ADRs
