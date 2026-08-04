# VRP Solver: Orquestación Inteligente para el Problema de Ruteamiento de Vehículos

**Autor:** Degnie  
**Docente:** GUERRA GRADOS, Luis Angel  
**Institución:** EP: Ciencia de la Computación — UNMSM  
**Contexto:** Evolución de un proyecto académico a una arquitectura orientada a producción.

Este proyecto resuelve el **Problema de Ruteamiento de Vehículos (VRP) Capacitado**, optimizando rutas logísticas para flotas de distribución. Pasa de un enfoque puramente teórico a un motor aplicable a escenarios reales, capaz de manejar ventanas de capacidad asimétricas y distancias geoespaciales reales (OSRM). 

Está diseñado para dueños de flotas que necesitan planificar operaciones diarias eficientes, operadores que gestionan asignaciones, y repartidores en calle.

---

## 🏛️ La Arquitectura Elegida (y lo que se descartó)

El proyecto utiliza una **Arquitectura Híbrida Python / C++**. 

*   **C++ (Core Algorítmico):** Se encarga exclusivamente de las tareas computacionalmente intensivas: evaluación de matrices de costo asimétricas y ejecución de heurísticas intensivas de búsqueda local (ej. 3-opt y Ruin-Recreate).
*   **Python (FastAPI):** Actúa como orquestador de alto nivel, manejando el dominio del negocio, la concurrencia, reglas de seguridad y API REST. La comunicación cruzada ocurre mediante *bindings* de `pybind11` pasando arrays de NumPy con *zero-copy*, evitando la costosa sobrecarga de serialización.

**Decisiones de Diseño Clave y Descartados (ADRs):**
*   **Se descartó compilar C++ dentro de los contenedores Docker:** Para mantener el principio de "imágenes ligeras" (RNF-004), el contenedor Docker del backend (`python:3.11-slim`) se ejecuta utilizando un *fallback* algorítmico 100% Python. Aunque es más lento, mantiene la exactitud funcional sin inflar el despliegue de producción con toolchains (CMake, GCC) innecesarios en runtime.
*   **Se descartó la calibración dinámica por Deep Reinforcement Learning (DRL):** Aunque figuraba en el plan inicial (ADR-003), se decidió mantener heurísticas deterministas (`Simulated Annealing`). Invertir en infraestructura de PyTorch para el runtime resultaba especulativo y añadía una capa de complejidad injustificada sin evidencia en métricas de negocio que demostrara pobre calidad en las rutas actuales.
*   **Base de datos Dual:** PostgreSQL garantiza las transacciones ACID y la integridad del equipo y configuración de flotas, mientras MongoDB almacena de manera flexible el alto volumen de datos no estructurados de las soluciones (coordenadas, secuencias y matrices).

---

## 🧗‍♂️ Retos Técnicos Superados

A lo largo del ciclo de vida del proyecto se abordaron casos límite reales de alta complejidad, purgados gracias a auditorías agresivas basadas en roles de usuario:

*   **Fugas Cruzadas de Datos (Multi-tenant accidental):** En un modelo donde los Repartidores y Dueños conviven en la misma base de datos, se detectó que endpoints de agregación filtraban métricas de la flota global a repartidores individuales. Se implementaron filtros incondicionales a nivel de adaptador de base de datos para aislar la lectura, garantizando que un actor sólo vea el grafo y los costos de su propia sub-ruta.
*   **NaN Silencioso de OSRM (Ruteo Geográfico):** OSRM retorna valores nulos en rutas desconectadas (islas, falta de cobertura de mapas). Originalmente, este `None` se casteaba en un `NaN` de `float64` en NumPy que atravesaba todas las reglas de negocio (ya que `NaN < 0` en IEEE 754 evalúa como `False`). El problema se resolvió inyectando un cortacircuito en la capa de red que activa un *fallback* automático a distancias euclidianas seguras sin corromper la matriz de costos en C++.
*   **Race Conditions en Catálogos Dinámicos:** La interfaz asincrónica de React (Frontend) permitía a un usuario borrar un vehículo del catálogo mientras su petición de creación HTTP seguía "en vuelo". Esto dejaba vehículos huérfanos fantasma persistidos en PostgreSQL. Se solucionó espejando referencias volátiles (`useRef`) en estados reactivos para deshabilitar interacciones destructivas interdependientes.

---

## 🧪 Cómo se Verifica (Metodología de Desarrollo)

El desarrollo del proyecto siguió un estricto proceso de ingeniería con separación de responsabilidades: **Especificación (Usuario) → Implementación → Auditoría y Verificación Automatizada.**

*   **Especificación Centralizada (`SPEC.md`):** Es la única fuente de verdad funcional (actualmente en `v1.2`).
*   **Trazabilidad 100%:** Cada regla del SPEC tiene su ID (ej. `RN-005`). En la suite automatizada, cada test cita a qué regla responde (`spec: RN-005`). El script `check_traceability.py` rompe la compilación (`make verify`) si existe una regla de negocio sin pruebas asociadas.
*   **Métricas de Verificación:** 
    *   `verify` corre un total de **240 tests integrales y unitarios**.
    *   Trazabilidad completa: **48 de 48 IDs cubiertos**.
    *   Pipeline CI/CD en GitHub Actions como compuerta obligatoria ante cada Pull Request.

---

## 🛑 Alcance y Límites Deliberados

Un proyecto maduro conoce sus fronteras. Las siguientes funciones están deliberadamente fuera de alcance para no comprometer el principio YAGNI (*You Aren't Gonna Need It*):

*   **Múltiples países o regiones geográficas simultáneas:** El extracto de OSRM está acotado exclusivamente a Perú (250MB pre-procesado) por objetivo de mercado local. Escalarlo es una tarea mecánica de infraestructura, no un problema arquitectónico pendiente.
*   **Múltiples Depósitos / Múltiples Ventanas de Tiempo Estrictas (VRPTW):** La heurística actual resuelve un único depósito y prioriza el enrutamiento puro por capacidades (CVRP).
*   **Validación C++ de Invariantes C++:** Se decidió intencionalmente mantener toda la validación lógica de invariantes (límites de carga, asignaciones) en la capa Python (pydantic/dataclasses), evitando duplicar código `is_valid()` en C++.

---

## 🚀 Quick Start

### Build & Run
```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Build C++ core
make build

# Run tests
make test

# Start API server
make run
```

### Entorno de Producción / Contenedores
```bash
# Frontend
docker build -t vrp-frontend frontend/
# Backend
docker build -f backend_python/Dockerfile -t vrp-backend .
```

---

## 📚 Documentación Adjunta

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Diseño técnico profundo
- **[API.md](docs/API.md)** — Especificación REST con ejemplos
- **[CREDITS.md](docs/CREDITS.md)** — Atribuciones académicas
- **[ADRs](docs/adr/)** — Decisiones arquitectónicas justificadas
