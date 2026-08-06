# Estrategia de Testing (VRP Solver)

## 1. Cobertura Exigida
- Trazabilidad estricta: 100% de las reglas definidas en `SPEC.md` deben estar cubiertas por al menos un test en la suite de pruebas. El script `check_traceability.py` audita esta correspondencia.
- No se impone un límite estricto de cobertura de código (ej. 95%), sino que se prioriza la trazabilidad por reglas funcionales.

## 2. Estrategias por Capa
- **API y Orquestación (Python):** Pruebas de integración (`pytest` con `TestClient`) que simulan flujos reales (creación de instancia, catálogos, solución) verificando las validaciones y reglas de negocio del `SPEC.md`.
- **Core Algorítmico (C++):** Pruebas unitarias nativas (ctest) enfocadas puramente en el desempeño matemático, exactitud de las heurísticas y operadores (Simulated Annealing, 3-opt, Ruin-Recreate).
- **Persistencia (PostgreSQL / MongoDB):** Pruebas de integración para asegurar ciclos completos de lectura/escritura sin pérdida y la reconexión frente a interrupciones.

## 3. Inyección de Fallos
- Se evalúa la robustez del sistema inyectando fallos controlados, como interrupciones simuladas en PostgreSQL (validación de reconexión), distancias nulas en OSRM (validación de fallback) y ausencia del binario compilado (fallback al motor Python).

## 4. Decisiones Históricas y Deuda Técnica
- Pruebas matemáticas puras en C++ e integraciones con servicios externos que no mapean de manera directa a una RN específica del negocio se mantienen en estado de cuarentena lógica. Esta es deuda técnica documentada que valida el mecanismo técnico profundo, cuya cantidad no puede incrementar sin la respectiva justificación en `SPEC.md`.
