# VRP Solver — Optimización del Problema de Ruteamiento de Vehículos

**Proyecto Final del curso: Análisis y Diseño de Algoritmos (2026.1)**
**EP: Ciencia de la Computación — UNMSM**

Desarrollamos una aplicación de escritorio en **C++17 con Qt** que resuelve el Problema de Ruteamiento de Vehículos (VRP) mediante la comparación experimental de heurísticas y metaheurísticas, cumpliendo con estrictos análisis de complejidad y escalabilidad.

## 👥 Equipo de Trabajo
* **Grupo de 3 integrantes**

**Docente:** GUERRA GRADOS, Luis Angel

---

## 📖 1. Descripción y Modelado del Problema

Abordamos el **Problema del Ruteamiento de Vehículos (VRP)**, que consiste en determinar un conjunto de rutas óptimas para una flota de vehículos que debe satisfacer la demanda de un conjunto de clientes desde un depósito central.

**Modelo Computacional:**
* **Grafo:** $G = (V, E)$, donde $V = \{0, 1, ..., n\}$ es el conjunto de vértices (0 es la matriz logística/depósito central, $1..n$ son las ciudades/clientes) y $E$ son las aristas que los conectan.
* **Costos:** Distancia euclidiana minimizada en todo el recorrido.
* **Restricción estricta:** La sumatoria de la demanda de los clientes en una ruta $R_k$ no puede superar la capacidad máxima del vehículo ($Q$). Todos los productos deben ser entregados.

---

## ⚙️ 2. Algoritmos y Análisis de Complejidad

Implementamos y comparamos experimentalmente dos enfoques algorítmicos. Ambos aseguran validez matemática y respeto de restricciones de capacidad.

### A. Algoritmo Constructivo: Greedy (Vecino Más Cercano)
Construimos la solución paso a paso, tomando siempre el nodo no visitado más cercano cuya demanda no exceda la capacidad restante del vehículo.
* **Complejidad Temporal:** $\mathcal{O}(n^2)$ — En el peor de los casos, buscamos la distancia mínima contra todos los nodos restantes en cada iteración.
* **Complejidad Espacial:** $\mathcal{O}(n)$ — Almacenamos estados de nodos visitados y la estructura de rutas.

### B. Metaheurística: Simulated Annealing (Recocido Simulado con 2-opt)
Aplicamos un algoritmo de búsqueda local que escapa de óptimos locales aceptando soluciones peores temporalmente, controladas por una función de temperatura decreciente. La vecindad se genera mediante *2-opt* intra-ruta.
* **Complejidad Temporal:** $\mathcal{O}(N_{iter})$ — Independiente de $n$ gracias al recálculo mediante $Delta$, donde $N_{iter} \approx \lceil \log(T_{min}/T_0) / \log(\alpha) \rceil$.
* **Complejidad Espacial:** $\mathcal{O}(n)$ — Mantenemos en memoria la solución actual y el estado vecino temporal.

---

## 🖥️ 3. Interfaz Gráfica de Usuario (GUI)

Desarrollamos la interfaz con el framework **Qt 6** y cumple con el 100% de los requisitos del sistema que definimos:
- [x] **Registrar configuración:** permite ingreso manual de clientes (ubicación X, Y, demanda) y configuración de capacidad máxima de vehículos ($Q$).
- [x] **Renderizado visual:** dibuja las rutas generadas en un plano cartesiano interactivo 2D (`QGraphicsView`), asignando colores por vehículo.
- [x] **Métricas en tiempo real:** muestra la distancia total recorrida y verifica la validez de la carga.
- [x] **Comparación experimental:** ejecuta múltiples algoritmos en paralelo para evaluar y mostrar métricas cruzadas.
- [x] **Cronometrado de CPU:** despliega el tiempo de ejecución (en milisegundos) aislando el cálculo lógico del renderizado.

---

## 📁 4. Estructura del Proyecto y Casos de Prueba

```text
VRP_Project/
├── CMakeLists.txt
├── README.md
├── data/                          # Dataset de experimentación
│   ├── pequenas/                  # n = 10, verificables manualmente
│   ├── medianas/                  # n = 10^3
│   ├── grandes/                   # n = 10^6
│   └── extremas/                  # n = 10^10 (Generadas on-the-fly)
├── docs/                          # Entregables académicos
│   ├── Informe_Final_VRP.pdf      # Análisis, pseudocódigos y escalabilidad
│   └── graficos_resultados/       # Gráficos de comparación algorítmica
└── src/
    ├── main.cpp                   
    ├── core/                      # Dominio matemático puro (Grafo, Nodos)
    ├── algorithms/                # Implementación de Greedy y SA
    ├── io/                        # Parsing tipo CVRPLIB
    └── gui/                       # Capa visual (Qt)
