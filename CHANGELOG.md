# Changelog

## [Sin publicar] — 2026-07-11 (iteración 4)

### Cambios (solo interfaz — sin tocar núcleo/algoritmos)

- **Tema visual vía QSS** (`resources/style.qss`, embebido por recurso Qt):
  radios de 6px, paleta neutra, CTA "Comparar ambos" en esmeralda
  (`#00875A`, mismo tono que usamos en RouteView), "Limpiar todo" con bajo
  peso visual (sin relleno, borde sutil).
- **Reorganizamos el panel izquierdo en un `QTabWidget`**: "Datos y
  Configuración" (capacidad, agregar cliente, tabla, cargar/limpiar) y
  "Simulación" (Greedy/SA/Comparar).
- **Accesibilidad**: le dimos a cada campo (X, Y, Demanda, Q) un `QLabel`
  buddy y `setAccessibleName()`; definimos un orden de tabulación explícito
  vía `setTabOrder()`.
- **Íconos SVG** (`resources/icons/`, vía `.qrc` + módulo Qt Svg) en los
  botones de cargar/limpiar/ejecutar/comparar.
- **Overlay de progreso**: agregamos un `QProgressBar` indeterminado, hijo
  directo del mapa (no del layout), que reposicionamos con un
  `eventFilter` en cada resize; aparece en `ejecutarAsync()` y se oculta
  en `onCalculoTerminado()`.
- **Log con HTML**: `log()` inyecta badges (✔ VÁLIDA / ✘ INVÁLIDA / ✘ ERROR)
  sobre los patrones de texto conocidos, en vez de texto plano.
- **RouteView**: adoptamos la paleta Okabe-Ito (colorblind-safe) + 4 estilos
  de línea cíclicos (sólida/rayada/punteada/raya-punto) para que las rutas
  no dependan solo del color; rediseñamos el depósito como un rombo navy
  con anillo blanco (antes, un cuadrado negro liso); agregamos LOD
  adaptativo en `wheelEvent()` (desactivamos el antialiasing durante el
  zoom y lo reactivamos ~100ms después de parar, vía `QTimer` single-shot).

### Decisiones que descartamos

- No descartamos nada explícitamente en esta iteración — nos enfocamos
  estrictamente en la interfaz y no tocamos factorías ni despliegue.

## [Sin publicar] — 2026-07-11 (iteración 3)

### Cambios

- **SA: presupuesto de iteraciones escalado por n, no solo por T0/alpha/Tmin.**
  El enfriamiento por defecto llegaba a `Tmin` en ~2300 pasos sin importar
  si la instancia tenía 10 o 10^6 clientes — con `n` grande, la inmensa
  mayoría de la solución nunca se tocaba. Ahora derivamos
  `maxIteracionesReales` de `n` (piso 2000, techo 2,000,000), y
  recalculamos el `alpha` efectivo (`pow(Tmin/T0, 1/maxIteracionesReales)`)
  para que el enfriamiento realmente tarde ese presupuesto en agotarse —
  cambiar solo el techo de iteraciones sin esto no alcanzaba, porque la
  condición `T > Tmin` seguía cortando el bucle en los mismos ~2300 pasos
  de siempre (lo verificamos empíricamente: sin este segundo ajuste la
  mejora de SA sobre Greedy en una instancia de 3000 clientes era de
  0.001%; con el alpha derivado, 0.82%).
- **SA: las iteraciones fallidas ya no enfrían.** Si `aplicar2Opt` no
  genera movimiento (`idxRuta == -1`, ruta elegida sin tamaño para un
  2-opt), la iteración hace `continue` sin bajar la temperatura — antes
  gastábamos "combustible" de enfriamiento en intentos que no movían nada.
  Agregamos una válvula de seguridad (tope de intentos totales) para el
  caso patológico de que ninguna ruta sea nunca elegible.
- **Corregimos el floating-point drift.** Cada 10,000 movimientos
  ACEPTADOS, recalculamos `costoActual` desde cero con `costoTotal()` en
  vez de seguir acumulando `+= delta` indefinidamente — con millones de
  sumas en punto flotante el error acumulado deja de ser despreciable.
- **`Instancia::nodo()` / `Solucion::ruta()` con `assert()` en vez de
  `throw`.** Son los getters de mayor tráfico del proyecto (SA los llama
  en cada iteración). `assert()` se compila a nada en Release (`NDEBUG`),
  así eliminamos el branching de validación del hot-loop; en builds Debug
  sigue atrapando índices inválidos igual que antes. Dejamos `depot()`
  (poco usado, no hot-path) con `throw`.
- **`GreedyNN`: agregamos `reserve()` en cada ruta.** Usamos una cota
  superior real (`min(n, Q+2)`, porque cada cliente pide al menos 1
  unidad) para evitar realocaciones por doblado de capacidad mientras la
  ruta crece. El pre-filtro de "cliente no cabe en la capacidad restante"
  ya lo teníamos desde la iteración anterior (lo documentamos mejor con un
  comentario).
- **`LectorInstancia::trim()` con `std::string_view`.** Ya no copia a
  `std::string` en cada llamada (se invoca varias veces por línea). Los
  dos puntos donde sí hace falta un `std::string` real —`std::stoi`
  (DIMENSION/CAPACITY, una vez por archivo) e `istringstream` (una vez
  por línea de datos, porque no tiene constructor desde `string_view` en
  C++17)— quedan con conversión explícita y comentada.
- **Tabla de clientes: `QTableWidget` → `QTableView` + `ClientesTableModel`.**
  El modelo nuevo (`QAbstractTableModel`, en `MainWindow.h`) lee directo de
  `const Instancia*` y genera cada celda on-demand en `data()` — O(1) por
  celda pedida, en vez de instanciar un `QTableWidgetItem` por cada una de
  las `4 × n` celdas de golpe (con `n` = 10^6, eso son millones de
  QObjects vivos solo para la tabla).
- **`RouteView`: puntos LOD sin `QPainterPath` de miles de elipses.**
  Con más de 500 nodos, los marcadores de cliente ya no se acumulan como
  curvas Bézier en un `QPainterPath` (caro de tesselar); los rasterizamos
  una sola vez con `QPainter::drawPoints` sobre un `QImage` cacheado
  (acotado a 2000px de lado para no pedir un bitmap gigante) y los
  insertamos como un único `QGraphicsPixmapItem`, escalado de vuelta al
  tamaño real de la escena.
- **`MainWindow::onCalculoTerminado()` con semántica de movimiento.** La
  solución (ganadora, en el caso de "Comparar") se traslada a
  `m_solucion` con `std::move()` en vez de copiarse. Además, si todos los
  resultados de una corrida fallan, limpiamos el mapa y `m_solucion` en
  vez de dejar pintada la solución de la corrida anterior.
- **Directorio de datos por defecto vía CMake.**
  `target_compile_definitions(VRP_Solver PRIVATE DEFAULT_DATA_DIR="...")`
  inyecta la ruta de `data/`; `onCargarInstancia()` abre el diálogo ahí en
  vez de a ciegas.

### Decisiones que descartamos

- **Automatizar `windeployqt` desde CMake.** Lo mantenemos como paso
  externo de CI/CD — `DEFAULT_DATA_DIR` es una constante de compilación,
  no despliegue, así que no contradice esta decisión previa.
- **Parámetros vía variables de entorno globales.** Preferimos pasar
  `DEFAULT_DATA_DIR` como definición de compilación directa (acoplamiento
  funcional simple) en vez de leer variables de entorno en runtime — es
  un proyecto académico/científico, no hace falta la indirección extra de
  configuración externa ni una factoría para eso.
- **Cambiar la ruta de `add_test(NAME test_core ...)`.** La consideramos
  quemada en algún momento, pero ya usa
  `${CMAKE_CURRENT_SOURCE_DIR}/data/ejemplo_10.vrp` — un path absoluto
  calculado en configure-time, correcto sin importar desde dónde
  invoquemos `ctest` ni dónde esté el directorio de build. No había nada
  que arreglar ahí; cambiarlo solo habría sido indirección cosmética.

## [Sin publicar] — 2026-07-11 (iteración 2)

### Cambios

- **`Solucion::esValida()` sin `std::set`.** El chequeo de clientes
  duplicados usa `std::vector<bool>` indexado por id (O(1) por inserción,
  sin fragmentar el heap con nodos de árbol) en vez de `std::set<int>`.
- **SA sin allocation en el hot-loop.** `aplicar2Opt` ya no arma un
  `std::vector<int>` de rutas candidatas en cada iteración; elegimos un
  índice de ruta al azar directo y descartamos la iteración (sin
  movimiento) si esa ruta no alcanza para un 2-opt real. También acotamos
  el exponente de `std::exp(-delta/T)` para no depender del underflow de
  punto flotante.
- **`LectorInstancia` sin vectores temporales duplicados.** Reemplazamos
  `xs`, `ys` y `demandas` (3 arreglos paralelos) por un único
  `std::vector<Cliente>` que se llena directo durante el parseo — evita
  mantener el doble de memoria viva hasta el final de la carga.
- **Renderizado por lotes (LOD) en `RouteView`.** Con más de 500 nodos,
  `dibujar()` deja de crear un `QGraphicsLineItem`/`QGraphicsEllipseItem`/
  `QGraphicsSimpleTextItem` por segmento y por cliente, y en su lugar traza
  cada ruta como un solo `QGraphicsPathItem` (un `QPainterPath` con todas
  las líneas) y todos los marcadores de cliente como un único
  `QGraphicsPathItem` más — de O(n) items a O(rutas). Por debajo del
  umbral, mantenemos el dibujo detallado (con etiquetas) igual.
- **Paso de instancia asíncrono sin copias extra.** `MainWindow::ejecutarAsync`
  toma un único snapshot (`std::make_shared<const Instancia>`) y lo captura
  por puntero en la lambda de `QtConcurrent::run`, en vez de copiar la
  `Instancia` otra vez al empaquetar la tarea.
- **Bloqueamos la UI mientras corre un cálculo.** `m_panelIzq` y la barra
  de menú se deshabilitan en `ejecutarAsync()` y se reactivan en
  `onCalculoTerminado()`, para que no se pueda mutar `m_instancia` (cargar
  otra instancia, agregar un cliente, cambiar Q) mientras el hilo de fondo
  todavía está resolviendo sobre el snapshot anterior.
- **Resultados por etiqueta, no por índice.** `onCalculoTerminado()` busca
  el resultado de "GREEDY"/"SA" por su campo `etiqueta` en vez de asumir
  `resultados[0]`/`resultados[1]`.
- **CMake:** agregamos `install(TARGETS ... RUNTIME DESTINATION bin)` +
  `install(DIRECTORY data/ ...)`, y activamos LTO
  (`INTERPROCEDURAL_OPTIMIZATION`) en Release cuando `check_ipo_supported()`
  lo confirma.

### Decisiones que descartamos

- **Factory dinámico para los algoritmos** y **automatización de
  `windeployqt`** — mantuvimos la misma decisión que en la iteración
  anterior (indirección sin beneficio real con solo dos algoritmos, y
  empaquetado fuera del alcance de esta ronda de rendimiento/concurrencia).

## [Sin publicar] — 2026-07-11

### Cambios

- **SA: delta O(1) real.** `SimulatedAnnealing::aplicar2Opt` ya no clona la
  solución completa ni recalcula `costoTotal()` en cada iteración; mutamos
  la ruta in-place y calculamos el delta mirando solo las 2 aristas rotas
  y las 2 nuevas. Si rechazamos el movimiento, lo revertimos invirtiendo
  el mismo segmento en vez de descartar una copia.
- **PRNG thread-safe.** Cambiamos el generador `mt19937` de
  `SimulatedAnnealing` de `static` (compartido, no seguro entre hilos) a
  `thread_local` (uno por hilo, sin locks) — necesario ahora que el
  solver corre en un `QThread` de fondo.
- **Greedy sin riesgo de bucle infinito.** `GreedyNN::resolver` valida al
  inicio que ningún cliente pida más que la capacidad `Q`; si eso ocurre,
  lanza `std::invalid_argument` en vez de generar rutas vacías para
  siempre. Además, reemplazamos `std::set<int>` de no-visitados por
  `std::vector<bool>` para mejor localidad de caché, y la búsqueda del
  vecino más cercano compara `distanciaCuadrada()` (sin `sqrt`).
- **`Instancia::distanciaCuadrada()`** nueva; la usamos en comparaciones
  de heurísticas (Greedy). Reservamos `distancia()` (con `sqrt`) para
  sumar costos reales.
- **Lectura de instancias defensiva.** `LectorInstancia::cargar` envuelve
  el parseo (`std::stoi`, secciones) en `try/catch`, valida `DIMENSION`
  contra un tope razonable antes de reservar memoria, y devuelve `false` +
  mensaje de error en vez de propagar excepciones.
- **GUI no bloqueante.** `MainWindow` corre `GreedyNN`/`SimulatedAnnealing`
  en un hilo de fondo vía `QtConcurrent::run` + `QFutureWatcher`, sobre una
  *copia* de la instancia (el hilo de fondo nunca toca `m_instancia` ni
  `m_solucion` — esos solo se leen/escriben desde el hilo de la UI al
  terminar el cálculo). Capturamos las excepciones del solver (p.ej.
  demanda > Q) y las mostramos como diálogo de error en vez de crashear.
- **`RouteView` sin recalcular el bounding box en cada repintado.**
  Separamos `mostrar()` (instancia nueva → recalcula bbox) de
  `mostrarSolucion()` (misma instancia, solo cambia la ruta a dibujar →
  reusa el bbox cacheado). `MainWindow` usa `mostrarSolucion()` después de
  correr un algoritmo.
- **CMake:** agregamos flags de optimización agresivas en Release
  (`-O3 -DNDEBUG` / `/O2 /DNDEBUG` en MSVC) cuando no especificamos
  `CMAKE_BUILD_TYPE`, y sumamos `enable_testing()` + `add_test()` para
  `test_core` (sin Qt) vía CTest.
- **`tests/test_core.cpp`** ya no tiene quemada la ruta
  `data/ejemplo_10.vrp`; la recibe por `argv[1]`.

### Decisiones que descartamos

- **Factory dinámico para los algoritmos** (registrar Greedy/SA por
  nombre en un mapa extensible en runtime). Solo tenemos dos algoritmos y
  los instanciamos directamente donde se usan; una factory es indirección
  sin beneficio hasta que exista un tercer algoritmo real.
- **Despliegue automático con `windeployqt`** integrado al build. Lo
  dejamos fuera de alcance de esta iteración (rendimiento + robustez); lo
  podemos agregar como paso de CI/empaquetado por separado cuando haga
  falta distribuir el `.exe`.
