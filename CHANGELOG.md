# Changelog

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
