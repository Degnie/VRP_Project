# VRP Solver — Greedy + Simulated Annealing

Proyecto del curso **Análisis y Diseño de Algoritmos (2026-I)**
E.P. Ciencias de la Computación — UNMSM

Aplicación de escritorio en **C++17 con Qt** que resuelve el
**Vehicle Routing Problem (VRP)** comparando dos enfoques:

- **Greedy — Vecino más cercano** (algoritmo constructivo, `O(n²)`)
- **Simulated Annealing con 2-opt** (metaheurística, `O(N_iter)`)

---

## Estructura del proyecto

```
VRP_Project/
├── CMakeLists.txt
├── README.md
├── data/                          # instancias de prueba
│   ├── ejemplo_10.vrp
│   └── ejemplo_20.vrp
└── src/
    ├── main.cpp                   # punto de entrada
    ├── core/                      # núcleo del problema (sin Qt)
    │   ├── Cliente.h
    │   ├── Instancia.h / .cpp
    │   └── Solucion.h / .cpp
    ├── algorithms/                # algoritmos
    │   ├── IVRPSolver.h           # interfaz común
    │   ├── GreedyNN.h / .cpp
    │   └── SimulatedAnnealing.h / .cpp
    ├── io/                        # lectura de archivos
    │   └── LectorInstancia.h / .cpp
    └── gui/                       # interfaz gráfica Qt
        ├── MainWindow.h / .cpp
        └── RouteView.h / .cpp
```

El núcleo (`core/`) y los algoritmos (`algorithms/`) **no dependen de Qt**,
así que se pueden probar y correr desde consola sin GUI si hiciera falta.

---

## Requisitos

- CMake ≥ 3.16
- Compilador con soporte C++17 (g++ 9+, clang 10+, MSVC 2019+)
- **Qt 6** (recomendado) o **Qt 5** — módulo *Widgets*

### Instalación de Qt en Windows

1. Descargar el instalador de: <https://www.qt.io/download-qt-installer>
2. Crear una cuenta gratuita.
3. Instalar **Qt 6.x** con el compilador **MinGW** o **MSVC**.
4. Verificar que `qmake` esté disponible en la variable `PATH`.

### Instalación de Qt en Linux (Ubuntu)

```bash
sudo apt install qt6-base-dev cmake g++
```

---

## Cómo compilar y ejecutar

Desde la carpeta raíz del proyecto:

```bash
mkdir build
cd build
cmake ..
cmake --build .
./VRP_Solver            # Linux / macOS
VRP_Solver.exe          # Windows
```

Si se usa Qt Creator, basta con abrir el archivo `CMakeLists.txt` como
proyecto y presionar *Ejecutar*.

---

## Cómo usar la aplicación

1. **Cargar una instancia** desde `Archivo → Cargar instancia...`
   (o con el botón "Cargar archivo..." del panel izquierdo).
   Ya vienen dos casos de ejemplo en la carpeta `data/`.

2. **Agregar clientes manualmente** con los campos `X`, `Y`, `Demanda`
   del panel izquierdo. El botón "Fijar" define la capacidad Q del vehículo.

3. **Ejecutar los algoritmos** con los botones:
   - `Ejecutar Greedy`
   - `Ejecutar SA`
   - `Comparar ambos` → corre los dos y muestra el mejor.

4. **Ver los resultados**:
   - El mapa central dibuja las rutas con un color distinto por vehículo.
   - El panel inferior lista el costo total, el tiempo, número de rutas
     y si la solución es válida.

---

## Formato del archivo de instancia

Es una versión simplificada del estándar **CVRPLIB**:

```
NAME : ejemplo_10
DIMENSION : 11
CAPACITY : 40
NODE_COORD_SECTION
1  50.0  50.0
2  20.0  25.0
...
DEMAND_SECTION
1  0
2  8
...
EOF
```

- `DIMENSION` incluye al depósito (n_clientes + 1).
- El primer nodo (id = 1) siempre es el depósito y su demanda es 0.
- Los ids del archivo van de 1 a DIMENSION; internamente el programa los
  reindexa como 0..DIMENSION-1.

---

## Parámetros del Simulated Annealing

Se pueden ajustar en `SimulatedAnnealing.h`. Los valores por defecto son:

| Parámetro | Valor | Significado |
|-----------|-------|-------------|
| `T0`      | 1000  | Temperatura inicial |
| `alpha`   | 0.995 | Tasa de enfriamiento (0 < α < 1) |
| `Tmin`    | 0.01  | Temperatura mínima de parada |

El número de iteraciones equivale a `⌈ log(Tmin/T0) / log(alpha) ⌉ ≈ 2 300`.

---

## Autores

- CABELLO VILLÓN, Emilio Denis Enrique — 24200086
- VERDE JARA, Leonel Edwuar — 24200209
- LOPEZ MONTALVO, Kevin Edu — 24200075

**Docente:** GUERRA GRADOS, Luis Angel
