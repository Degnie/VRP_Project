# Changelog

## [1.3.0] - 2026-07-11
### Añadido (Added)
* Tema visual vía QSS (`resources/style.qss`, embebido por recurso Qt): radios de 6px, paleta neutra, CTA "Comparar ambos" en esmeralda (`#00875A`, mismo tono que `RouteView`), "Limpiar todo" con bajo peso visual (sin relleno, borde sutil).
* Panel izquierdo reorganizado en un `QTabWidget`: "Datos y Configuración" (capacidad, agregar cliente, tabla, cargar/limpiar) y "Simulación" (Greedy/SA/Comparar).
* Accesibilidad: `QLabel` buddy y `setAccessibleName()` para cada campo (X, Y, Demanda, Q); orden de tabulación explícito vía `setTabOrder()`.
* Íconos SVG (`resources/icons/`, vía `.qrc` + módulo Qt Svg) en los botones de cargar/limpiar/ejecutar/comparar.
* Overlay de progreso: `QProgressBar` indeterminado, hijo directo del mapa (no del layout), reposicionado con un `eventFilter` en cada resize; aparece en `ejecutarAsync()` y se oculta en `onCalculoTerminado()`.
* Log con HTML: `log()` inyecta badges (VÁLIDA / INVÁLIDA / ERROR) sobre los patrones de texto conocidos, en vez de texto plano.
* `RouteView`: paleta Okabe-Ito (colorblind-safe) + 4 estilos de línea cíclicos (sólida/rayada/punteada/raya-punto) para que las rutas no dependan solo del color; depósito rediseñado como rombo navy con anillo blanco (antes, cuadrado negro liso); LOD adaptativo en `wheelEvent()` (desactiva antialiasing durante el zoom, lo reactiva ~100ms después vía `QTimer` single-shot).

### Cambiado (Changed)
* Ninguno en esta iteración (iteración de solo interfaz, sin tocar núcleo/algoritmos).

### Arreglado (Fixed)
* Ninguno en esta iteración.

### Rechazado / Descartado (Rejected/Discarded)
* No se descartó nada explícitamente en esta iteración; el foco estuvo estrictamente en la interfaz, sin tocar factorías ni despliegue.

## [1.2.0] - 2026-07-11
### Añadido (Added)
* Directorio de datos por defecto vía CMake: `target_compile_definitions(VRP_Solver PRIVATE DEFAULT_DATA_DIR="...")` inyecta la ruta de `data/`; `onCargarInstancia()` abre el diálogo ahí en vez de a ciegas.

### Cambiado (Changed)
* SA: presupuesto de iteraciones escalado por `n`, no solo por T0/alpha/Tmin. El enfriamiento por defecto llegaba a `Tmin` en ~2300 pasos sin importar si la instancia tenía 10 o 10^6 clientes. Ahora `maxIteracionesReales` se deriva de `n` (piso 2000, techo 2,000,000) y se recalcula el `alpha` efectivo (`pow(Tmin/T0, 1/maxIteracionesReales)`) para que el enfriamiento tarde ese presupuesto en agotarse. Verificado empíricamente en una instancia de 3000 clientes: sin el ajuste de alpha, la mejora de SA sobre Greedy era 0.001%; con el alpha derivado, 0.82%.
* `Instancia::nodo()` / `Solucion::ruta()`: `assert()` en vez de `throw`. Son los getters de mayor tráfico (SA los llama en cada iteración); `assert()` se compila a nada en Release (`NDEBUG`), eliminando el branching del hot-loop, y sigue atrapando índices inválidos en Debug. `depot()` (poco usado, no hot-path) queda con `throw`.
* `GreedyNN`: `reserve()` en cada ruta con cota superior real (`min(n, Q+2)`, cada cliente pide al menos 1 unidad) para evitar realocaciones por doblado de capacidad mientras la ruta crece.
* `LectorInstancia::trim()` migrado a `std::string_view` (ya no copia a `std::string` en cada llamada, se invoca varias veces por línea). Los dos puntos que sí necesitan `std::string` real (`std::stoi` para DIMENSION/CAPACITY, e `istringstream` por línea de datos, sin constructor desde `string_view` en C++17) quedan con conversión explícita y comentada.
* Tabla de clientes: `QTableWidget` → `QTableView` + `ClientesTableModel` (`QAbstractTableModel` en `MainWindow.h`) que lee directo de `const Instancia*` y genera cada celda on-demand en `data()` — O(1) por celda pedida, en vez de instanciar un `QTableWidgetItem` por cada una de las `4 × n` celdas de golpe (con `n` = 10^6, millones de QObjects vivos solo para la tabla).
* `RouteView`: puntos LOD sin `QPainterPath` de miles de elipses. Con más de 500 nodos, los marcadores de cliente se rasterizan una sola vez con `QPainter::drawPoints` sobre un `QImage` cacheado (acotado a 2000px de lado) y se insertan como un único `QGraphicsPixmapItem`, escalado de vuelta al tamaño real de la escena.
* `MainWindow::onCalculoTerminado()`: la solución ganadora se traslada a `m_solucion` con `std::move()` en vez de copiarse.

### Arreglado (Fixed)
* SA: las iteraciones fallidas ya no enfrían. Si `aplicar2Opt` no genera movimiento (`idxRuta == -1`, ruta elegida sin tamaño para un 2-opt), la iteración hace `continue` sin bajar la temperatura; se agregó una válvula de seguridad (tope de intentos totales) para el caso patológico de que ninguna ruta sea nunca elegible.
* Floating-point drift corregido: cada 10,000 movimientos ACEPTADOS, `costoActual` se recalcula desde cero con `costoTotal()` en vez de seguir acumulando `+= delta` indefinidamente, porque con millones de sumas en punto flotante el error acumulado deja de ser despreciable.
* `MainWindow::onCalculoTerminado()`: si todos los resultados de una corrida fallan, se limpia el mapa y `m_solucion` en vez de dejar pintada la solución de la corrida anterior.

### Rechazado / Descartado (Rejected/Discarded)
* Automatizar `windeployqt` desde CMake: se mantiene como paso externo de CI/CD (`DEFAULT_DATA_DIR` es una constante de compilación, no despliegue, no contradice esta decisión previa).
* Parámetros vía variables de entorno globales: se prefirió pasar `DEFAULT_DATA_DIR` como definición de compilación directa (acoplamiento funcional simple) en vez de leer variables de entorno en runtime — proyecto académico/científico, sin necesidad de indirección extra de configuración externa ni una factoría para eso.
* Cambiar la ruta de `add_test(NAME test_core ...)`: ya usa `${CMAKE_CURRENT_SOURCE_DIR}/data/ejemplo_10.vrp`, un path absoluto calculado en configure-time, correcto sin importar desde dónde se invoque `ctest` ni dónde esté el directorio de build. No había nada que arreglar; cambiarlo habría sido indirección cosmética.

## [1.1.0] - 2026-07-11
### Añadido (Added)
* CMake: `install(TARGETS ... RUNTIME DESTINATION bin)` + `install(DIRECTORY data/ ...)`, y LTO (`INTERPROCEDURAL_OPTIMIZATION`) en Release cuando `check_ipo_supported()` lo confirma.

### Cambiado (Changed)
* `Solucion::esValida()` sin `std::set`: el chequeo de clientes duplicados usa `std::vector<bool>` indexado por id (O(1) por inserción, sin fragmentar el heap con nodos de árbol) en vez de `std::set<int>`.
* SA sin allocation en el hot-loop: `aplicar2Opt` ya no arma un `std::vector<int>` de rutas candidatas en cada iteración; se elige un índice de ruta al azar directo y se descarta la iteración (sin movimiento) si esa ruta no alcanza para un 2-opt real. También se acota el exponente de `std::exp(-delta/T)` para no depender del underflow de punto flotante.
* `LectorInstancia` sin vectores temporales duplicados: `xs`, `ys` y `demandas` (3 arreglos paralelos) se reemplazan por un único `std::vector<Cliente>` que se llena directo durante el parseo, evitando mantener el doble de memoria viva hasta el final de la carga.
* Renderizado por lotes (LOD) en `RouteView`: con más de 500 nodos, `dibujar()` deja de crear un `QGraphicsLineItem`/`QGraphicsEllipseItem`/`QGraphicsSimpleTextItem` por segmento y por cliente, y traza cada ruta como un solo `QGraphicsPathItem` y todos los marcadores de cliente como otro único `QGraphicsPathItem` — de O(n) items a O(rutas). Por debajo del umbral se mantiene el dibujo detallado (con etiquetas).
* Paso de instancia asíncrono sin copias extra: `MainWindow::ejecutarAsync` toma un único snapshot (`std::make_shared<const Instancia>`) y lo captura por puntero en la lambda de `QtConcurrent::run`, en vez de copiar la `Instancia` otra vez al empaquetar la tarea.
* Resultados por etiqueta, no por índice: `onCalculoTerminado()` busca el resultado de "GREEDY"/"SA" por su campo `etiqueta` en vez de asumir `resultados[0]`/`resultados[1]`.

### Arreglado (Fixed)
* UI bloqueada mientras corre un cálculo: `m_panelIzq` y la barra de menú se deshabilitan en `ejecutarAsync()` y se reactivan en `onCalculoTerminado()`, para que no se pueda mutar `m_instancia` (cargar otra instancia, agregar un cliente, cambiar Q) mientras el hilo de fondo todavía resuelve sobre el snapshot anterior.

### Rechazado / Descartado (Rejected/Discarded)
* Factory dinámico para los algoritmos: misma decisión que la iteración anterior, indirección sin beneficio real con solo dos algoritmos.
* Automatización de `windeployqt`: empaquetado fuera del alcance de esta ronda de rendimiento/concurrencia.

## [1.0.0] - 2026-07-11
### Añadido (Added)
* `Instancia::distanciaCuadrada()`, usada en comparaciones de heurísticas (Greedy); `distancia()` (con `sqrt`) queda reservada para sumar costos reales.
* CMake: flags de optimización agresivas en Release (`-O3 -DNDEBUG` / `/O2 /DNDEBUG` en MSVC) cuando no se especifica `CMAKE_BUILD_TYPE`, y `enable_testing()` + `add_test()` para `test_core` (sin Qt) vía CTest.

### Cambiado (Changed)
* SA: delta O(1) real. `SimulatedAnnealing::aplicar2Opt` ya no clona la solución completa ni recalcula `costoTotal()` en cada iteración; muta la ruta in-place y calcula el delta mirando solo las 2 aristas rotas y las 2 nuevas. Si el movimiento se rechaza, se revierte invirtiendo el mismo segmento en vez de descartar una copia.
* Greedy: reemplazo de `std::set<int>` de no-visitados por `std::vector<bool>` para mejor localidad de caché; la búsqueda del vecino más cercano compara `distanciaCuadrada()` (sin `sqrt`).
* `RouteView` sin recalcular el bounding box en cada repintado: `mostrar()` (instancia nueva, recalcula bbox) se separa de `mostrarSolucion()` (misma instancia, solo cambia la ruta a dibujar, reusa el bbox cacheado). `MainWindow` usa `mostrarSolucion()` después de correr un algoritmo.
* `tests/test_core.cpp` ya no tiene quemada la ruta `data/ejemplo_10.vrp`; la recibe por `argv[1]`.

### Arreglado (Fixed)
* PRNG thread-safe: el generador `mt19937` de `SimulatedAnnealing` pasa de `static` (compartido, no seguro entre hilos) a `thread_local` (uno por hilo, sin locks), necesario ahora que el solver corre en un `QThread` de fondo.
* Greedy sin riesgo de bucle infinito: `GreedyNN::resolver` valida al inicio que ningún cliente pida más que la capacidad `Q`; si eso ocurre, lanza `std::invalid_argument` en vez de generar rutas vacías para siempre.
* Lectura de instancias defensiva: `LectorInstancia::cargar` envuelve el parseo (`std::stoi`, secciones) en `try/catch`, valida `DIMENSION` contra un tope razonable antes de reservar memoria, y devuelve `false` + mensaje de error en vez de propagar excepciones.
* GUI no bloqueante: `MainWindow` corre `GreedyNN`/`SimulatedAnnealing` en un hilo de fondo vía `QtConcurrent::run` + `QFutureWatcher`, sobre una *copia* de la instancia (el hilo de fondo nunca toca `m_instancia` ni `m_solucion`). Se capturan las excepciones del solver (p.ej. demanda > Q) y se muestran como diálogo de error en vez de crashear.

### Rechazado / Descartado (Rejected/Discarded)
* Factory dinámico para los algoritmos (registrar Greedy/SA por nombre en un mapa extensible en runtime): solo hay dos algoritmos, instanciados directamente donde se usan; una factory es indirección sin beneficio hasta que exista un tercer algoritmo real.
* Despliegue automático con `windeployqt` integrado al build: fuera de alcance de esta iteración (rendimiento + robustez); se puede agregar como paso de CI/empaquetado separado cuando haga falta distribuir el `.exe`.
