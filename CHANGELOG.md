# Changelog

## [Sin publicar] — 2026-07-11 (iteración 2)

### Cambios

- **`Solucion::esValida()` sin `std::set`.** El chequeo de clientes
  duplicados usa `std::vector<bool>` indexado por id (O(1) por inserción,
  sin fragmentar el heap con nodos de árbol) en vez de `std::set<int>`.
- **SA sin allocation en el hot-loop.** `aplicar2Opt` ya no arma un
  `std::vector<int>` de rutas candidatas en cada iteración; elige un
  índice de ruta al azar directo y descarta la iteración (sin movimiento)
  si esa ruta no alcanza para un 2-opt real. También se acotó el
  exponente de `std::exp(-delta/T)` para no depender del underflow de
  punto flotante.
- **`LectorInstancia` sin vectores temporales duplicados.** `xs`, `ys` y
  `demandas` (3 arreglos paralelos) se reemplazaron por un único
  `std::vector<Cliente>` que se llena directo durante el parseo — evita
  mantener el doble de memoria viva hasta el final de la carga.
- **Renderizado por lotes (LOD) en `RouteView`.** Con más de 500 nodos,
  `dibujar()` deja de crear un `QGraphicsLineItem`/`QGraphicsEllipseItem`/
  `QGraphicsSimpleTextItem` por segmento y por cliente, y en su lugar traza
  cada ruta como un solo `QGraphicsPathItem` (un `QPainterPath` con todas
  las líneas) y todos los marcadores de cliente como un único
  `QGraphicsPathItem` más — de O(n) items a O(rutas). Por debajo del
  umbral, el dibujo detallado (con etiquetas) se mantiene igual.
- **Paso de instancia asíncrono sin copias extra.** `MainWindow::ejecutarAsync`
  toma un único snapshot (`std::make_shared<const Instancia>`) y lo captura
  por puntero en la lambda de `QtConcurrent::run`, en vez de copiar la
  `Instancia` otra vez al empaquetar la tarea.
- **UI bloqueada mientras corre un cálculo.** `m_panelIzq` y la barra de
  menú se deshabilitan en `ejecutarAsync()` y se reactivan en
  `onCalculoTerminado()`, para que no se pueda mutar `m_instancia` (cargar
  otra instancia, agregar un cliente, cambiar Q) mientras el hilo de fondo
  todavía está resolviendo sobre el snapshot anterior.
- **Resultados por etiqueta, no por índice.** `onCalculoTerminado()` busca
  el resultado de "GREEDY"/"SA" por su campo `etiqueta` en vez de asumir
  `resultados[0]`/`resultados[1]`.
- **CMake:** `install(TARGETS ... RUNTIME DESTINATION bin)` +
  `install(DIRECTORY data/ ...)`, y LTO (`INTERPROCEDURAL_OPTIMIZATION`)
  activado en Release cuando `check_ipo_supported()` lo confirma.

### Rechazado en esta sesión

- **Factory dinámico para los algoritmos** y **automatización de
  `windeployqt`** — restricción explícita del prompt de esta iteración;
  se mantiene la misma decisión que en la iteración anterior (indirección
  sin beneficio real con solo dos algoritmos, y empaquetado fuera del
  alcance de esta ronda de rendimiento/concurrencia).
- **Reemplazar la ruta de `add_test(NAME test_core ...)`.** Se pidió
  "despatearla" por considerarla quemada, pero ya usa
  `${CMAKE_CURRENT_SOURCE_DIR}/data/ejemplo_10.vrp` — un path absoluto
  calculado en configure-time, correcto sin importar desde dónde se
  invoque `ctest` ni dónde esté el directorio de build. No había nada que
  arreglar ahí; cambiarlo solo habría sido indirección cosmética.

## [Sin publicar] — 2026-07-11

### Cambios

- **SA: delta O(1) real.** `SimulatedAnnealing::aplicar2Opt` ya no clona la
  solución completa ni recalcula `costoTotal()` en cada iteración; muta la
  ruta in-place y calcula el delta mirando solo las 2 aristas rotas y las 2
  nuevas. Si el movimiento se rechaza, se revierte invirtiendo el mismo
  segmento en vez de descartar una copia.
- **PRNG thread-safe.** El generador `mt19937` de `SimulatedAnnealing` pasó
  de `static` (compartido, no seguro entre hilos) a `thread_local` (uno por
  hilo, sin locks) — necesario ahora que el solver corre en un `QThread` de
  fondo.
- **Greedy sin riesgo de bucle infinito.** `GreedyNN::resolver` valida al
  inicio que ningún cliente pida más que la capacidad `Q`; si eso ocurre,
  lanza `std::invalid_argument` en vez de generar rutas vacías para
  siempre. Además, `std::set<int>` de no-visitados se reemplazó por
  `std::vector<bool>` para mejor localidad de caché, y la búsqueda del
  vecino más cercano compara `distanciaCuadrada()` (sin `sqrt`).
- **`Instancia::distanciaCuadrada()`** nueva; se usa en comparaciones de
  heurísticas (Greedy). `distancia()` (con `sqrt`) se reserva para sumar
  costos reales.
- **Lectura de instancias defensiva.** `LectorInstancia::cargar` envuelve el
  parseo (`std::stoi`, secciones) en `try/catch`, valida `DIMENSION` contra
  un tope razonable antes de reservar memoria, y devuelve `false` + mensaje
  de error en vez de propagar excepciones.
- **GUI no bloqueante.** `MainWindow` corre `GreedyNN`/`SimulatedAnnealing`
  en un hilo de fondo vía `QtConcurrent::run` + `QFutureWatcher`, sobre una
  *copia* de la instancia (el hilo de fondo nunca toca `m_instancia` ni
  `m_solucion` — esos solo se leen/escriben desde el hilo de la UI al
  terminar el cálculo). Excepciones del solver (p.ej. demanda > Q) se
  capturan y se muestran como diálogo de error en vez de crashear.
- **`RouteView` sin recalcular el bounding box en cada repintado.** Se
  separó en `mostrar()` (instancia nueva → recalcula bbox) y
  `mostrarSolucion()` (misma instancia, solo cambia la ruta a dibujar →
  reusa el bbox cacheado). `MainWindow` usa `mostrarSolucion()` después de
  correr un algoritmo.
- **CMake:** flags de optimización agresivas en Release (`-O3 -DNDEBUG` /
  `/O2 /DNDEBUG` en MSVC) cuando no se especifica `CMAKE_BUILD_TYPE`.
  Se agregó `enable_testing()` + `add_test()` para `test_core` (sin Qt) vía
  CTest.
- **`tests/test_core.cpp`** ya no tiene quemada la ruta
  `data/ejemplo_10.vrp`; la recibe por `argv[1]`.

### Rechazado en esta sesión

- **Factory dinámico para los algoritmos** (registrar Greedy/SA por nombre
  en un mapa extensible en runtime). Solo hay dos algoritmos y se
  instancian directamente donde se usan; una factory es indirección sin
  beneficio hasta que exista un tercer algoritmo real.
- **Despliegue automático con `windeployqt`** integrado al build. Fuera de
  alcance de esta iteración (rendimiento + robustez); se puede agregar
  como paso de CI/empaquetado por separado cuando haga falta distribuir el
  `.exe`.
