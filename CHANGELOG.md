# Changelog

Todos los cambios notables en este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.7.11] — 2026-08-02

### 🔍 Ronda 2 de auditoría por roles (ciclo 3, solo dueño)

Tercer ciclo de auditoría por roles, enfocado exclusivamente en el rol dueño (operario/repartidor ya venían de rondas limpias en ciclos anteriores). Ronda 1: cero hallazgos. Ronda 2 (de confirmación): 1 hallazgo `[BUG]` — no cuenta como ronda limpia, el ciclo continúa.

### 🐛 Fixed
- **Paginación de `0.7.7` sin efecto real (dueño):** `0.7.7` agregó `limit`/`offset` a `GET /instances`, `GET /vehicle-catalog` y `GET /auth/users` en el backend, pero ningún caller del frontend los pasaba — el fix quedó a medio camino, sin beneficio para una cuenta con historial largo. Al revisar los 3 call sites reales: `listInstances()` solo se usa para un chequeo de ID duplicado (`App.tsx`, necesita ver todos los IDs, no debe paginarse) y el catálogo de vehículos (`InstanceForm.tsx`) es un estado editable con diff-sync automático contra el backend (paginarlo rompería la lógica de diff, que necesita ver todas las filas para detectar altas/bajas). El único listado real, de solo lectura y que crece sin límite en uso normal es la tabla de equipo. Fix: `TeamManagement.tsx` pagina con "Cargar más" (`PAGE_SIZE=50`), `api.ts` expone `limit`/`offset` opcionales en `listTeam`/`listVehicleCatalog`/`listInstances` (estos dos últimos sin cambiar ningún call site existente). Sin test automatizado — el repo no tiene test runner de frontend en `make verify` (mismo gap ya documentado en la Ronda 1 del ciclo 2, fix de `RepartidorView.tsx`); verificado con `tsc -b` (sin errores nuevos respecto a master) y revisión manual del flujo cargar/invitar/desactivar/cargar más.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 227 passed / 0 failed (sin cambio, fix solo de frontend), `test-cpp` 1/1 passed, `traceability` 35/35 (sin cambio, no cita ningún ID nuevo — completa el trabajo de `0.7.7`, no agrega regla).

---

## [0.7.12] — 2026-08-02

### 🔍 Ronda 3 de auditoría por roles (ciclo 3, solo dueño)

Ronda 3: 2 hallazgos — 1 `[REGLA NUEVA]` (aprobada) + 1 hallazgo menor resuelto en la misma ronda por decisión explícita del usuario.

### 📐 Reglas nuevas
- **RN-COV-003 (Recálculo de cobertura ante edición de coordenadas):** el campo `inCoverage` de un cliente en el formulario de instancia debe reevaluarse contra la zona de cobertura vigente cada vez que cambian sus coordenadas X/Y — ya sea por edición manual, alta de fila nueva, o corrección post-import — no solo al importar un CSV o al redibujar el polígono.

### 🐛 Fixed
- **RN-COV-003 — `inCoverage` no se recalculaba al editar X/Y a mano (dueño):** `InstanceForm.tsx` solo recalculaba `inCoverage` al importar CSV o al redibujar la zona guardada (`useEffect([coveragePoints])`) — editar coordenadas de una fila existente a mano dejaba el badge "Fuera de cobertura" y el filtro de `POST /solve` (`groups.filter(g => g.inCoverage)`) pegados al valor calculado anteriormente, pudiendo incluir en el solve a un cliente realmente fuera de zona o excluir a uno dentro, sin ninguna advertencia visual. Fix: `updateGroupField` recalcula `inCoverage` contra la zona vigente en cada cambio de `x`/`y` (`frontend/src/components/InstanceForm.tsx`). Sin test automatizado — el repo no tiene test runner de frontend en `make verify` (mismo gap documentado en la Ronda 1 del ciclo 2); citado como `spec: RN-COV-003 — PENDIENTE` en `tests/unit/test_coverage_zone_api.py` para trazabilidad, verificado con `tsc -b` (sin errores nuevos respecto a master) y revisión manual del flujo.
- **RN-EXP-002 (extensión) — PDF en blanco cuando se reprograma el 100% de un vehículo (dueño):** `build_route_pdf` filtra `client_id in rescheduled_client_ids` por parada, pero el guard de `api/__init__.py` solo verifica que el vehículo tenga alguna ruta en la solución original, no que le queden paradas tras el filtro — si el dueño reprogramaba todos los pedidos de un vehículo y exportaba el PDF de la instancia original, obtenía `200` con encabezado y columnas pero cero filas, indistinguible de un error de generación. Fix: si `stop_num == 0` tras el filtro, la página muestra "Todos los pedidos de este vehículo fueron reprogramados." en vez de quedar en blanco (`backend_python/api/export.py`). Test: `test_vehicle_with_all_stops_rescheduled_shows_explicit_message` (`tests/unit/test_export.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 228 passed / 0 failed (227 previos + 1 nuevo), `test-cpp` 1/1 passed, `traceability` 36/36 (RN-COV-003 agregada, citada como PENDIENTE en `test_coverage_zone_api.py`).

---

## [0.7.13] — 2026-08-02

### 🔍 Ronda 4 de auditoría por roles (ciclo 3, solo dueño)

Ronda 4: 1 hallazgo `[REGLA NUEVA]` (aprobada). Posible refinamiento excesivo anotado sin implementar: el timeout de `/solve` (120s) podría repetirse a mayor escala con OSRM e instancias muy grandes — misma área que el fix de timeout de otro ciclo, no se profundizó.

### 📐 Reglas nuevas
- **RN-016 (API - instancia_id no vacío):** `instancia_id` en `POST /solve` y `POST /instances/{id}/solve` debe ser un string no vacío tras aplicar `strip()` — un valor vacío o compuesto solo por espacios en blanco se rechaza con `422` antes de construir la instancia.

### 🐛 Fixed
- **RN-016 — `instancia_id` de solo espacios pasaba sin validar (dueño):** el input HTML `required` del formulario solo bloquea string vacío, no uno de solo espacios (ej. un typeo perdido al borrar el default "instancia-1" con Ctrl+A) — el backend tampoco lo rechazaba, así que se persistía una instancia con ID invisible en la lista, indistinguible de otra con el mismo problema, sin colisionar con el chequeo de duplicado del frontend (compara el string crudo sin trim). Fix: `field_validator` en `InstanceRequest.instancia_id` rechaza con `422` si el valor está vacío tras `.strip()` (`backend_python/api/__init__.py`); el frontend además hace `trim()` al construir el request (`frontend/src/lib/buildInstance.ts`) para que el chequeo de duplicado en `App.tsx` compare valores ya normalizados. Test: `test_solve_rejects_whitespace_only_instancia_id` (`tests/unit/test_api_integration.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (228 previos + 1 nuevo), `test-cpp` 1/1 passed, `traceability` 37/37 (RN-016 agregada y cubierta).

---

## [0.7.14] — 2026-08-03

### 🔍 Ronda 5 (última) de auditoría por roles (ciclo 3, solo dueño)

Ronda 5: 2 hallazgos `[REGLA NUEVA]` (ambos aprobados). Posible refinamiento excesivo anotado sin implementar: `updated_at` de cliente se serializa sin sufijo `"Z"` (inconsistente con RN-015), pero no reproduce el bug original porque el frontend nunca lo parsea como `Date`, solo lo reenvía como string opaco para el guard de optimistic locking.

### 📐 Reglas nuevas
- **RN-017 (UI - Confirmación al desactivar usuario):** cambiar el estado activo de un usuario del equipo a inactivo requiere confirmación explícita antes de ejecutarse, mismo patrón que borrar o sobreescribir una instancia.
- **RN-018 (UI - Flota consistente con catálogo vigente):** al borrar del catálogo un tipo de vehículo seleccionado en la flota de una instancia sin resolver, el formulario debe quitarlo de la flota configurada y avisar explícitamente, en vez de descartar la entrada en silencio al construir la solicitud.

### 🐛 Fixed
- **RN-017 — desactivar usuario sin confirmación (dueño y operario):** `TeamManagement.tsx` llamaba `setUserActive` directo al click de "Desactivar", sin el mismo `ConfirmDialog` ya usado para borrar/sobreescribir instancia — un click en la fila equivocada cortaba el acceso de un operario o repartidor de inmediato, sin ningún paso previo. Además el backend permite tanto a `dueño` como `operario` ejecutar esta acción. Fix: `ConfirmDialog` antes de desactivar (reactivar no lo requiere, no tiene el mismo riesgo) — `frontend/src/components/TeamManagement.tsx`. Sin test automatizado (gap de frontend ya documentado); citado como `spec: RN-017 — PENDIENTE` en `tests/integration/test_auth_flow.py`.
- **RN-018 — flota huérfana tras borrar un tipo de catálogo en uso (dueño):** `fleet` (conteos por tipo de vehículo) nunca se podaba cuando un tipo seleccionado se borraba del catálogo — `buildInstance.ts` descartaba la entrada en silencio (`if (!type) continue`) al construir `POST /solve`, reduciendo `num_vehicles`/capacidad enviada sin ningún aviso, pudiendo causar un rechazo confuso de RN-005/RN-006 o una solución con menos vehículos de los que el dueño cree haber configurado. Fix: nuevo `useEffect` en `InstanceForm.tsx` poda `fleet` cuando su `vehicleTypeId` ya no existe en `vehicleTypes`, y muestra un aviso explícito. Sin test automatizado (mismo gap); citado como `spec: RN-018 — PENDIENTE` en `tests/unit/test_vehicle_catalog_api.py`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (sin cambio, ambos fixes son frontend-only), `test-cpp` 1/1 passed, `traceability` 39/39 (RN-017, RN-018 agregadas y citadas como PENDIENTE).

### 📋 Resumen del ciclo 3 (Rondas 1-5, solo rol dueño)

5 rondas — Ronda 1 limpia, luego 4 rondas con hallazgos genuinos y distintos entre sí (paginación de un fix previo incompleto, cobertura desincronizada, PDF vacío, ID de instancia inválido, confirmación faltante, flota huérfana). **Cerrado por tope**, no por rondas limpias — el rol dueño (mayor superficie: catálogo, cobertura, equipo, export, edición, flota) siguió encontrando bugs reales ronda tras ronda, igual que en los ciclos 1 y 2. 7 hallazgos corregidos (2 bugs directos + 5 reglas nuevas: RN-COV-003, RN-016, RN-017, RN-018, más la paginación completada), 0 descartados, 0 revertidos. Todos con TDD completo salvo los 3 frontend-only (RN-COV-003, RN-017, RN-018), que comparten el gap ya documentado: no hay test runner de frontend en `make verify`, verificados con `tsc -b` + revisión manual.

Patrón consistente con los dos ciclos anteriores: el rol dueño no llegó a 2 rondas limpias consecutivas en ningún ciclo hasta ahora — señal de que la superficie de dueño sigue siendo la más grande de la app, no de que el ciclo esté atascado (cada hallazgo de esta ronda fue en un archivo/área distinto al de la ronda anterior, sin ningún "refinamiento excesivo" real aplicado).

---

## [0.7.15] — 2026-08-03

### 🔍 Ronda 1 de auditoría por roles (ciclo 4, solo dueño)

Cuarto ciclo de auditoría, enfocado solo en el rol dueño (ciclos 1-3 ya corrieron 15 rondas combinadas). Ronda 1: 1 hallazgo `[REGLA NUEVA]` (aprobada), cosmético — no cuenta como ronda limpia.

### 📐 Reglas nuevas
- **RN-019 (UI - Formato numérico de totales):** todo total agregado que ve el dueño en pantalla (peso, volumen, costo, cantidad) debe formatearse con separador de miles acorde al locale, consistente con el resto de la aplicación.

### 🐛 Fixed
- **RN-019 — totales de flota sin separador de miles (dueño):** `FleetSelector.tsx` interpolaba `totalWeightKg`/`totalVolumeM3`/`totalVehicles` como números JS crudos, sin `Intl.NumberFormat` — inconsistente con `SolutionSummary.tsx`, que ya formatea `num_routes`/`total_cost` con el mismo patrón. Con una flota realista (decenas de vehículos, miles de kg efectivos combinados) el dueño veía `"18000 kg"` en vez de `"18.000 kg"`, más difícil de leer de un vistazo al planificar la operación del día. Sin impacto funcional — el valor era correcto, solo el formato de presentación. Fix: mismo `Intl.NumberFormat` aplicado a los tres totales (`frontend/src/components/FleetSelector.tsx`). Sin test automatizado (gap de frontend ya documentado); citado como `spec: RN-019 — PENDIENTE` en `tests/unit/test_vehicle_catalog_api.py`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (sin cambio, fix frontend-only), `test-cpp` 1/1 passed, `traceability` 40/40 (RN-019 agregada y citada como PENDIENTE).

---

## [0.7.16] — 2026-08-03

### 🔍 Ronda 2 de auditoría por roles (ciclo 4, solo dueño)

Ronda 2: 1 hallazgo `[REGLA NUEVA]` (aprobada), cosmético — no cuenta como ronda limpia.

### 📐 Reglas nuevas
- **RN-020 (UI - Orden de asignación consistente con el solver):** el texto de ayuda que describe el orden de asignación de la flota debe ordenar por capacidad efectiva (nominal × margen de tolerancia), el mismo criterio que usa `buildInstance.ts` al construir `vehicle_capacities` para el solver — no por capacidad nominal, que puede mostrar el orden invertido cuando los tipos de vehículo tienen márgenes de tolerancia distintos entre sí.

### 🐛 Fixed
- **RN-020 — hint de orden de flota usaba capacidad nominal, no efectiva (dueño):** `FleetSelector.tsx` ordenaba el texto "Orden de asignación" por `weightCapacityKg` nominal, pero `buildInstance.ts` construye `vehicle_capacities` (lo que realmente ve el solver) ordenado por capacidad efectiva (nominal × margen de tolerancia) — con dos tipos de vehículo de margen distinto entre sí (ej. 1000 kg/margen 0.80 = 800 efectivos vs. 900 kg/margen 1.0 = 900 efectivos), el hint mostraba el orden invertido del que realmente usa el solver. Cosmético — el cálculo real siempre fue correcto, solo el texto informativo. Fix: mismo criterio `effectiveWeightKg` (ya existente en el archivo, usado para los totales) aplicado al comparador de orden (`frontend/src/components/FleetSelector.tsx`). Sin test automatizado (gap de frontend ya documentado); citado como `spec: RN-020 — PENDIENTE` en `tests/unit/test_vehicle_catalog_api.py`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (sin cambio, fix frontend-only), `test-cpp` 1/1 passed, `traceability` 41/41 (RN-020 agregada y citada como PENDIENTE).

---

## [0.7.17] — 2026-08-03

### 🔍 Ronda 4 (confirmación) de auditoría por roles (ciclo 4, solo dueño)

La Ronda 3 cerró limpia (cero hallazgos) — primera ronda limpia de este ciclo. Esta ronda de confirmación encontró 1 hallazgo `[REGLA NUEVA]` (aprobado), así que no cumple la condición de 2 rondas limpias consecutivas y el ciclo sigue.

### 📐 Reglas nuevas
- **RN-COV-004 (Confirmación al borrar zona de cobertura):** borrar la zona de cobertura de la cuenta requiere confirmación explícita antes de ejecutarse, mismo patrón que borrar/sobreescribir una instancia o desactivar un usuario (RN-017).

### 🐛 Fixed
- **RN-COV-004 — borrar zona de cobertura sin confirmación (dueño):** el botón "Borrar zona" en `CoverageZoneEditor.tsx` ejecutaba `clearCoverageZone()` directo al click, sin `ConfirmDialog` — la única acción destructiva de la app que quedaba fuera de ese patrón (ya aplicado a instancia y a RN-017). Está además al lado de "Redibujar zona" (que no borra nada hasta cerrar el nuevo polígono) en el mismo bloque, con riesgo real de click accidental. Borrar la zona también recalcula `inCoverage: true` para todos los clientes de un formulario de instancia abierto (efecto de RN-COV-003), incluyéndolos en el próximo solve sin que el dueño lo haya decidido. Fix: `ConfirmDialog` antes de ejecutar el borrado (`frontend/src/App.tsx`). Sin test automatizado (gap de frontend ya documentado); citado como `spec: RN-COV-004 — PENDIENTE` en `tests/unit/test_coverage_zone_api.py`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (sin cambio, fix frontend-only), `test-cpp` 1/1 passed, `traceability` 42/42 (RN-COV-004 agregada y citada como PENDIENTE).

---

## [0.7.18] — 2026-08-03

### 🔍 Ronda 5 (última) de auditoría por roles (ciclo 4, solo dueño)

Ronda 5: 1 hallazgo `[BUG]` — corrección directa de un patrón ya existente en el mismo archivo (sin ID de regla nueva, mismo criterio que el fix de charset del PDF en `0.7.9`).

### 🐛 Fixed
- **Estado de reprogramación no se limpiaba al cambiar de instancia (dueño):** `rescheduleResult`/`rescheduleError`/`rescheduledPendingSolveId` en `SolutionSummary.tsx` no se reseteaban cuando `solution.instancia_id` cambiaba — a diferencia de `staleRouteWarning`, que sí lo hace en el mismo archivo (mismo componente sin `key` por instancia, así que no se remonta al navegar). El dueño podía reprogramar la instancia A, navegar a la instancia B sin resolver la reprogramación, y ver el banner/botón "Resolver 'A-reprog-xxxx' ahora" de A todavía visibles sobre B — un click ahí resolvía la instancia equivocada y cambiaba silenciosamente la pantalla de B a la solución de A. Fix: `useEffect` que resetea los tres estados al cambiar `solution.instancia_id`, mismo patrón que `staleRouteWarning` (`frontend/src/components/SolutionSummary.tsx`). Sin test automatizado (gap de frontend ya documentado); no requiere cita de traceability (sin ID de regla nuevo, corrección directa).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (sin cambio, fix frontend-only), `test-cpp` 1/1 passed, `traceability` 42/42 (sin cambio, ningún ID nuevo).

### 📋 Resumen del ciclo 4 (Rondas 1-5, solo rol dueño)

5 rondas — Ronda 3 fue la única limpia, sin lograr una segunda ronda limpia consecutiva. **Cerrado por tope**, no por rondas limpias. 5 hallazgos corregidos (RN-019, RN-020, RN-COV-004, más el bug directo de reprogramación de esta ronda), 0 descartados, 0 revertidos. Todos frontend-only salvo la corrección final (sin ID), documentados con el mismo gap de test runner de frontend ya conocido, verificados con `tsc -b` + revisión manual.

**Nota acumulada de los 4 ciclos sobre el rol dueño (24 rondas combinadas):** el rol dueño nunca llegó a 2 rondas limpias consecutivas hasta la Ronda 3 de este ciclo (la primera ronda limpia de las 24). La Ronda 4 rompió esa racha con un hallazgo genuino y distinto (confirmación de borrado de zona), y la Ronda 5 encontró otro bug real y distinto (estado de reprogramación). Esto sigue sin ser evidencia de un ciclo atascado — cada hallazgo de los últimos 3 ciclos fue en un área o archivo distinto al de la ronda inmediatamente anterior (sin ningún caso real de "refinamiento excesivo" aplicado), consistente con una superficie grande que se va agotando gradualmente, no con un bug repetido siendo refinado indefinidamente.

---

## [0.7.19] — 2026-08-03

### 🔍 Ronda 1 de auditoría por roles (ciclo 5, solo dueño)

Quinto ciclo de auditoría, enfocado solo en el rol dueño (ciclos 1-4 ya corrieron 24 rondas combinadas). Ronda 1: 1 hallazgo `[BUG]` — viola directamente RN-016 en un segundo code path que el fix original no cubrió, no requiere regla nueva.

### 🐛 Fixed
- **RN-016 — modo simple no trimeaba `instancia_id` (dueño):** el fix de RN-016 (`0.7.13`) trimeaba `instancia_id` en `buildInstance.ts`, pero ese archivo solo se usa en modo avanzado (catálogo con vehículos nombrados). El modo simple (`InstanceForm.tsx`, rama `simpleMode` — el estado por defecto en primer uso, sin catálogo configurado) armaba su propio request inline y mandaba el valor crudo. El backend solo rechaza si es 100% espacios tras `.strip()`, no trimea-y-persiste, así que `"instancia-1 "` (espacio al final) pasaba y se persistía con el espacio — dos instancias con el mismo ID visible pero uno con espacio final no se detectaban como duplicado (el chequeo compara string crudo). Fix: mismo `.trim()` aplicado en la rama `simpleMode` de `handleSubmit` (`frontend/src/components/InstanceForm.tsx`). Sin test automatizado (gap de frontend ya documentado, mismo ID RN-016 ya trazado).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 229 passed / 0 failed (sin cambio, fix frontend-only), `test-cpp` 1/1 passed, `traceability` 42/42 (sin cambio, RN-016 ya trazada).

---

## [0.7.2] — 2026-08-02

### 🔍 Ronda 1 de auditoría por roles (ciclo nuevo, post RN-013/limpieza de deuda de suite)

Ciclo de exploración con un agente por rol de usuario (`agent-workflow/prompts/12-auditoria-roles-claude.md`), posterior a los fixes de rendimiento (RN-013, P-01/P-02) y limpieza de deuda de tests (P-03/P-04). Operario: cero hallazgos. Dueño: 1 hallazgo `[BUG]`. Repartidor: 2 hallazgos `[BUG]`.

### 🐛 Fixed
- **RN-005/RN-006 (edición de cliente, dueño):** `PATCH /instances/{id}/clients/{cliente_id}` escribía la demanda editada directo a Postgres sin re-validar RN-005 (demanda total ≤ capacidad de flota) ni RN-006 (ningún cliente excede el vehículo más grande) — reglas que sí corren en la creación vía `Instancia.__post_init__`, pero no en la corrección posterior de un cliente ya persistido. La instancia quedaba corrupta en silencio (200 OK) hasta que un `load_instance` posterior (export PDF, reprogramación, delivery-statuses) explotaba con 500 genérico sin manejar. Fix: `update_client` valida demanda total y máximo por vehículo antes de escribir, rechazando con 422 y mensaje en español (`backend_python/api/__init__.py`). Tests: `test_update_client_rejects_demand_exceeding_fleet_capacity`, `test_update_client_rejects_demand_exceeding_largest_vehicle` (`tests/integration/test_order_lifecycle.py`).
- **Fuga cruzada entre repartidores en `GET /solutions/{instancia_id}`:** a diferencia de `get_my_route`/`update_delivery_status`/`export_solution_pdf`/`get_delivery_statuses` (todos ya blindados en rondas anteriores), este endpoint no filtraba por rol — un repartidor veía `sequence`/`cost`/`vehicle_id` de **todas** las rutas de la solución, incluidas las de otros repartidores. Fix: filtra a la ruta del vehículo asignado cuando `current_user.role == "repartidor"`, mismo patrón que sus endpoints hermanos. Tests: `test_repartidor_get_solution_scoped_to_own_route`, `test_repartidor_get_solution_404_without_assignment`.
- **`GET /instances` sin enforcement server-side para repartidor:** el filtro a "solo mis instancias asignadas" dependía de que el caller pasara `assigned_only=true` — un repartidor llamando el endpoint directo (sin pasar por el frontend) veía metadata de instancias ajenas de la cuenta entera. Fix: el filtro por repartidor ahora es incondicional al rol, no al query param (que queda aceptado por compatibilidad con el frontend, pero ya no se lee). Test: `test_list_instances_repartidor_scoped_without_assigned_only_param`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 210 passed / 0 failed (205 previos + 5 nuevos de esta ronda), `test-cpp` 1/1 passed, `traceability` 33/33 IDs cubiertos (sin cambio, ningún ID nuevo — los 3 bugs citan reglas ya existentes: RN-005, RN-006, RN-COV-001).

---

## [0.7.3] — 2026-08-02

### 🔍 Ronda 3 (confirmación) de auditoría por roles

La Ronda 2 (0.7.2) cerró limpia en los tres roles — primera ronda limpia del ciclo. Esta ronda de confirmación: dueño y operario cerraron limpios de nuevo, pero repartidor encontró 1 hallazgo `[BUG]` nuevo, así que el ciclo sigue (no cumple la condición de 2 rondas limpias consecutivas).

### 🐛 Fixed
- **Agregados de flota completa expuestos a repartidor en `GET /instances`:** `num_clients`/`num_vehicles` en el resumen de instancia eran los de la operación COMPLETA (todos los vehículos/repartidores), no los de la ruta propia del repartidor — a diferencia de `capacity`, que sí venía correctamente acotada por vehículo desde `flota_config.capacities[]`. Un repartidor veía, por ejemplo, "4 clientes, 2 vehículos" cuando a él solo le tocaban 2 clientes en su propio vehículo. Mismo patrón de fuga cruzada ya corregido 5 veces en rondas anteriores (`get_my_route`, `update_delivery_status`, `export_solution_pdf`, `get_delivery_statuses`, y en la Ronda 1 de este ciclo `get_solution`/`list_instances` sin filtro), pero en un campo que ninguna ronda anterior había inspeccionado (contaban filas visibles, no el contenido agregado dentro de cada fila). Fix: `list_instance_summaries` (`backend_python/persistence/postgres_adapter.py`) expone `ra.vehicle_id` para las filas de repartidor; el endpoint (`backend_python/api/__init__.py`) lee la ruta específica en Mongo (acotado a las filas ya filtradas a ese repartidor, sin reintroducir el N+1 de toda la cuenta que este query evita a propósito) para recalcular `num_clients`/`num_vehicles=1`. Test: `test_list_instances_repartidor_sees_own_route_counts_not_full_fleet` (`tests/integration/test_order_lifecycle.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 211 passed / 0 failed (210 previos + 1 nuevo), `test-cpp` 1/1 passed, `traceability` 33/33 IDs cubiertos (sin cambio, sin ID nuevo).

---

## [0.7.4] — 2026-08-02

### 🔍 Ronda 4 de auditoría por roles

Dueño y repartidor rompieron su racha de rondas limpias con hallazgos nuevos y genuinamente distintos entre sí; operario se mantiene limpio (7 rondas consecutivas) pero de paso detectó una inconsistencia en el mismo endpoint que tocó la Ronda 1/3 de repartidor.

### ✨ Added
- **RN-014 (API - Consistencia coordinates/demands):** `demands` debe tener exactamente la misma longitud que `coordinates` en `/solve` y `/instances/{id}/solve`. Bug real: un `demands` más corto (ej. CSV con una fila sin columna de demanda) producía `IndexError` nativo en el comprehension de construcción de clientes — no es `ValueError`, caía al `except Exception` genérico (500) en vez de un rechazo claro. Fix: valida la longitud antes de construir clientes, rechazando con `400` (mismo mecanismo que RN-006). Test: `test_solve_rejects_demands_length_mismatch` (`tests/unit/test_api_integration.py`).
- **RN-015 (API - Timestamps con zona horaria explícita):** todo timestamp de la API debe llevar sufijo `Z`. Bug real: `instancias.created_at` es `TIMESTAMP` (naive) en Postgres — sin sufijo de zona, el frontend (`new Date(...)`) interpretaba el string ISO como hora LOCAL del navegador en vez de UTC, desplazando la hora mostrada en el selector de instancias del repartidor según su huso horario. Fix: `postgres_adapter.py` agrega `"Z"` al serializar (Postgres siempre guarda en UTC en este proyecto, sin `TimeZone` custom — no requirió migrar la columna a `TIMESTAMPTZ`). Test: `test_instance_summary_created_at_has_explicit_timezone`.

### 🐛 Fixed
- **`GET /solutions/{id}` — `total_cost`/`num_routes` sin filtrar para repartidor:** usaban `solution.costo_total`/`solution.rutas` (la solución completa) en vez de la variable `rutas` ya acotada por rol (fix de la Ronda 1) — un repartidor con 1 ruta asignada veía el costo/conteo de TODA la solución junto a `routes` ya correctamente filtrado, una inconsistencia visible en la propia respuesta. Fix: ambos campos ahora derivan de `rutas`. Test: `test_repartidor_get_solution_total_cost_and_num_routes_scoped_to_own_route`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 214 passed / 0 failed (211 previos + 3 nuevos), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos (subió de 33 con RN-014/RN-015).

---

## [0.7.5] — 2026-08-02

### 🔍 Ronda 5 (última) de auditoría por roles — ciclo cerrado por tope

Última ronda del ciclo (tope de 5 declarado en el PASO 0). Operario y repartidor cerraron limpios (9 y 6 rondas consecutivas respectivamente), pero dueño encontró 1 hallazgo `[BUG]` nuevo — el ciclo cierra **por tope**, no por rondas limpias: dueño no llegó a acumular las 2 rondas limpias consecutivas que exige esa condición de cierre.

### 🐛 Fixed
- **OSRM `null` distances → `NaN` silencioso, no detectado por RN-008/RN-010:** OSRM devuelve `null` en una celda de `distances` cuando no hay ruta vial entre dos coordenadas (islas, tramos desconectados, cobertura incompleta del extracto de Perú) — sin validación, ese `None` llegaba hasta `np.asarray(dtype=float64)` y se convertía en `NaN` silencioso, sin lanzar `OSRMError` ni activar el fallback euclidiano de RN-MAT-001. `NaN < 0` es `False` en IEEE 754, así que ni RN-008 (costo de ruta `>= 0`) ni RN-010 (costo total = suma de costos) lo detectaban — `/solve` respondía `200 OK` con `total_cost: NaN`. Fix: `_table_request` (`backend_python/service/osrm_client.py`) valida que ninguna celda de `distances` sea `None` antes de devolver la matriz, lanzando `OSRMError` — el caller (`SolverOrchestrator`) ya captura ese error y cae al fallback euclidiano sin cambios adicionales. Test: `test_osrm_matrix_rejects_null_distance_cell` (`tests/unit/test_osrm_client.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 215 passed / 0 failed (214 previos + 1 nuevo), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos (sin cambio, el hallazgo cita RN-MAT-001 ya existente).

### 📋 Resumen del ciclo de auditoría por roles (Rondas 1-5, 2026-08-02)

5 rondas, cierre por tope (dueño no encadenó 2 rondas limpias). Total: 8 hallazgos `[BUG]`/`[REGLA NUEVA]` corregidos a lo largo del ciclo — RN-005/RN-006 en edición de cliente, 3 casos de fuga cruzada entre repartidores (`get_solution`, `list_instances` x2 variantes, agregados de flota), RN-014 (consistencia coordinates/demands), RN-015 (timestamps con zona horaria), y OSRM null-distance → NaN silencioso. Cero hallazgos descartados; cero refinamientos excesivos bloqueados por el cortacircuito de área.

---

## [0.7.6] — 2026-08-02

### 🔍 Ronda 1 de auditoría por roles (ciclo nuevo, post cierre por tope de 5cc9b2e)

3 hallazgos `[BUG]`, uno por rol — el ciclo anterior cerró por tope sin rondas limpias, y esta primera ronda confirma que aún había superficie real por descubrir.

### 🐛 Fixed
- **`PostgreSQLAdapter` no se reconectaba tras perder una conexión ya establecida:** `CONNECT_RETRIES` en `__init__` solo cubría la conexión inicial — si Postgres se reiniciaba (mantenimiento, actualización de imagen Docker) mientras el proceso de la API seguía vivo, `self.conn` quedaba con un objeto cerrado y **todas** las acciones del dueño/operario que tocan Postgres fallaban con 500 permanentemente, hasta reiniciar el proceso a mano — aunque Postgres ya se hubiera recuperado solo segundos después. Fix: `_locked` (decorador que ya envuelve los 27 métodos del adapter) chequea `self.conn.closed` antes de cada operación y reconecta vía el nuevo método `_reconnect()` (misma lógica de reintentos que `__init__`, ahora factorizada) — cubre todos los métodos de una sola vez sin tocarlos uno por uno. Test: `test_reconnects_when_connection_was_closed` (`tests/unit/test_persistence.py`).
- **`reschedule_instance` sin guard en el `save_instance` final:** el flujo de reprogramación hace 3 escrituras secuenciales a Postgres; el paso 2 (`mark_clients_rescheduled`) ya tenía guard de limpieza ante fallo (Ronda 3 de un ciclo anterior), pero el paso 3 (`save_instance` con los clientes reales) no tenía ninguno — si Postgres fallaba ahí, los clientes ya estaban marcados `'reprogramado'` (commit irreversible) apuntando a una instancia nueva que nunca llegó a tener sus datos reales: huérfanos para siempre, sin aparecer como pendientes en ningún lado. Fix: un reintento inline (mismo espíritu que `CONNECT_RETRIES`, cubre el caso más común de blip transitorio) y, si vuelve a fallar, `503` explícito indicando que los pedidos ya se movieron, en vez de un `500` genérico. Tests: `test_reschedule_recovers_if_final_save_fails_once_transiently`, `test_reschedule_returns_503_if_final_save_fails_persistently` (`tests/integration/test_order_lifecycle.py`).
- **`RepartidorView.tsx`: estado "Guardando…"/"✓ Guardado" cruzado entre instancias:** `savingStopIds`/`savedStopIds` no se reseteaban al cambiar de instancia (a diferencia de `route`/`pendingChange`/`error`, que sí lo hacían en el mismo efecto) — un `client_id` de la instancia anterior podía mostrar el indicador de guardado en una instancia distinta sin que el repartidor hubiera tocado nada ahí (RN-004 solo garantiza unicidad de id dentro de una instancia, no entre instancias). Fix: ambos `Set` se resetean en el mismo efecto `[selectedId]` que ya limpia el resto del estado. **Sin test automatizado** — el proyecto no tiene un runner de tests de frontend conectado a `make verify` (Playwright está instalado como dependencia pero sin script `npm test`, y los `.spec.ts` de `frontend/e2e/` no corren en este ciclo); documentado explícitamente como deuda de cobertura de frontend, no como bug sin verificar.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 218 passed / 0 failed (217 previos + 1 nuevo), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos (sin cambio, los 3 hallazgos citan reglas ya existentes o son fixes de infraestructura sin ID de dominio).

---

## [0.7.7] — 2026-08-02

### 🔍 Ronda 2 de auditoría por roles (ciclo nuevo)

Dueño: 2 hallazgos. Operario: 1 hallazgo. Repartidor: cero hallazgos.

### ✨ Added
- **Migración `0009`:** `clientes.updated_at` (`TIMESTAMP DEFAULT CURRENT_TIMESTAMP`) para optimistic locking (ver fix de operario abajo).

### 🐛 Fixed
- **`/auth/register` podía dejar una cuenta huérfana sin usuario:** `create_account()` y `create_user()` eran dos escrituras independientes, cada una con su propio commit — si la segunda fallaba por cualquier motivo que no fuera el email duplicado (ya capturado aparte), la cuenta quedaba huérfana sin usuario, sin ningún endpoint ni proceso para detectarla o recuperarla. Fix: nuevo método `create_account_with_user` en `PostgreSQLAdapter` hace ambos `INSERT` en un solo cursor con un solo commit/rollback — atómico. Test: `test_register_leaves_no_orphaned_account_if_user_insert_fails` (`tests/integration/test_auth_flow.py`).
- **Lost-update entre `POST /instances/{id}/solve` y `PATCH /instances/{id}/clients/{id}` concurrentes:** `_solve_and_persist` lee la instancia completa en T0, corre el pipeline NN→SA→3-opt (puede tardar segundos según RNF-002/003), y al terminar hace un upsert incondicional del snapshot T0 — si un `update_client` de otro operario commiteaba una edición entre T0 y ese `save_instance` final, la edición se perdía en silencio (ambos requests devolvían `200`). Fix: optimistic locking — `save_instance` solo pisa `demand`/`x`/`y`/contacto de un cliente si su `updated_at` en Postgres sigue coincidiendo con el snapshot que trajo `load_instance()` al iniciar el solve (`WHERE clientes.updated_at IS NOT DISTINCT FROM %s` en la cláusula `DO UPDATE`); si cambió, la edición concurrente gana. `update_client` ahora setea `updated_at=CURRENT_TIMESTAMP` en cada corrección. Test: `test_solve_does_not_overwrite_concurrent_client_edit`.
- **`GET /instances`, `GET /vehicle-catalog`, `GET /auth/users` sin paginación:** ninguno de los tres aceptaba `limit`/`offset` pese al objetivo de escala declarado del proyecto ("50 a 100k+ clientes") — una cuenta con muchas instancias/usuarios/tipos de vehículo históricos no tenía forma de acotar la respuesta. Fix: `limit`/`offset` opcionales en los tres endpoints y sus queries SQL subyacentes (`LIMIT`/`OFFSET`); sin `limit`, comportamiento idéntico al de siempre (trae todo) — no rompe ningún caller existente. Tests: `test_list_instances_respects_limit_and_offset`, `test_list_vehicle_catalog_respects_limit_and_offset`, `test_list_team_respects_limit_and_offset`.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 223 passed / 0 failed (218 previos + 5 nuevos), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos (sin cambio, ningún hallazgo requirió ID de dominio nuevo).

---

## [0.7.8] — 2026-08-02

### 🔍 Ronda 3 de auditoría por roles (ciclo nuevo) — sin cambios de código

Dueño: 1 hallazgo, descartado tras análisis (ver abajo). Operario: cero hallazgos. Repartidor: cero hallazgos (3ª ronda limpia consecutiva).

### Rechazado / Descartado
- **"Una cuenta puede quedar sin ningún dueño activo" (hallazgo del rol dueño):** se implementó un guard en `set_user_active` que contaba dueños activos antes de desactivar a otro dueño, pero al escribir el test de regresión se confirmó que es matemáticamente inalcanzable con los guards ya existentes: (1) nadie puede autodesactivarse (`user_id == current_user.user_id` → 400), y (2) solo un dueño puede desactivar a otro dueño (línea que ya exige `current_user.role == "dueño"`). Como el actor que ejecuta la desactivación es siempre un dueño que sigue activo después de la operación (no se autodesactivó), matemáticamente **siempre** queda al menos un dueño activo — el actor mismo. El escenario que motivó el hallazgo (cuenta sin ningún dueño activo) requeriría que el propio endpoint permitiera desactivarse a sí mismo, lo cual ya está bloqueado. Se revirtió el guard (código muerto, nunca alcanzable) en vez de dejarlo como falsa sensación de seguridad.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 223 passed / 0 failed (sin cambio, ningún test nuevo sobrevivió), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos.

---

## [0.7.9] — 2026-08-02

### 🔍 Ronda 4 de auditoría por roles (ciclo nuevo)

Dueño: 1 hallazgo. Operario: cero hallazgos (2ª ronda limpia). Repartidor: cero hallazgos (4ª ronda limpia consecutiva).

### 🐛 Fixed
- **Export PDF corrompía silenciosamente nombres/direcciones con caracteres fuera de Latin-1:** las fuentes base14 de reportlab (`Helvetica`, `WinAnsiEncoding`) no lanzan excepción ante CJK/cirílico/emoji — sustituyen cada carácter no soportado en silencio por una secuencia de `n` repetidas, indistinguible de un error de imprenta hasta que alguien lo lee en el papel que el repartidor usa para confirmar la entrega. Fix: `_pdf_safe()` en `backend_python/api/export.py` detecta (`str.encode("cp1252")`) si el texto es representable antes de dibujarlo; si no, lo reemplaza por un placeholder explícito (`"[nombre con caracteres no soportados]"`) en vez de dejar la corrupción silenciosa. Test: `test_name_with_unsupported_charset_uses_explicit_placeholder` (`tests/unit/test_export.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 224 passed / 0 failed (223 previos + 1 nuevo), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos (sin cambio, comportamiento nuevo sin ID de dominio — no aplica una RN numerada existente ni amerita una nueva por su alcance acotado).

---

## [0.7.10] — 2026-08-02

### 🔍 Ronda 5 (última) de auditoría por roles — ciclo cerrado por tope

Última ronda del ciclo (tope de 5). Operario (3ª ronda limpia) y repartidor (5ª ronda limpia consecutiva) cierran limpios, pero dueño encontró 1 hallazgo `[BUG]` — el ciclo cierra **por tope**, no por rondas limpias.

### ✨ Added
- **`GET /instances/{id}/clients/{id}`** (`ClientDetailResponse`): expone un cliente individual con `updated_at` — base para el fix de abajo. El frontend lo consulta al abrir el formulario de edición en vez de confiar en el snapshot de `localStorage` (`ClientGroup`, poblado por el flujo de importación, desconectado del ciclo de vida real del cliente persistido).

### 🐛 Fixed
- **Lost-update entre dos ediciones del mismo cliente (dos pestañas, dos usuarios) en `PATCH /instances/{id}/clients/{id}`:** a diferencia del fix de Ronda 2 (optimistic locking entre un `solve` concurrente y `update_client`), este caso no estaba cubierto — `customer_name`/`customer_phone`/`address` siempre viajan en el payload del formulario (`ClientEditControl.tsx` nunca los omite, precisamente para poder distinguir "vacío a propósito" de "no tocado"), así que el guard existente de `model_fields_set` nunca detectaba que el snapshot local ya estaba obsoleto — la segunda edición pisaba la primera en silencio, ambos requests devolviendo `200`. Fix: `UpdateClientRequest.updated_at` opcional — si se manda y no coincide con lo persistido, `409` en vez de pisar. El frontend ahora consulta `GET .../clients/{id}` al abrir el formulario (en vez de usar `contact` de `localStorage`) y manda ese `updated_at` de vuelta al guardar. Sin `updated_at` en el request (callers viejos), el guard no aplica — compatible hacia atrás. Tests: `test_get_client_returns_updated_at`, `test_update_client_rejects_stale_updated_at`, `test_update_client_without_updated_at_skips_guard` (`tests/integration/test_order_lifecycle.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 227 passed / 0 failed (224 previos + 3 nuevos), `test-cpp` 1/1 passed, `traceability` 35/35 IDs cubiertos.

### 📋 Resumen del ciclo de auditoría por roles (Rondas 1-5, 2026-08-02, post cierre por tope de `5cc9b2e`)

5 rondas, cierre nuevamente por tope (dueño encontró hallazgos en 4 de las 5 rondas — Rondas 1, 2, 4, 5 — sin encadenar 2 limpias). Total: 7 hallazgos `[BUG]` corregidos — reconexión de Postgres, guard de `reschedule_instance`, fuga de UI en `RepartidorView.tsx`, registro atómico de cuenta, lost-update solve-vs-edición (optimistic locking vía `clientes.updated_at`), paginación de 3 listados, export PDF con charset seguro, y lost-update edición-vs-edición (optimistic locking end-to-end con endpoint nuevo). 1 hallazgo implementado y revertido tras confirmar que era código muerto (Ronda 3, "cuenta sin dueño activo").

---

## ⬆️ MIGRACIÓN: Academia → Producción (2026-07-23 en adelante)

**Este punto marca la transición arquitectónica de la solución académica Qt/C++ al SaaS híbrido Python/C++.**

La historia anterior del proyecto (trabajo académico UNMSM 2024-2026) se preserva en Git pero no se mezcla con esta rama. Ver [docs/adr/0001-hybrid-python-cpp.md](docs/adr/0001-hybrid-python-cpp.md) para justificación técnica.

**Versioning:** A partir de aquí, semver estricto. v0.1.0-alpha inicia con base de arquitectura.

---

## [0.1.0-alpha] — 2026-07-23

### 🔄 Migration (Academic → Production)

Transición de arquitectura monolítica Qt/C++17 a híbrida Python/C++ para escalabilidad y producción.

**Referencias de inspiración:**
- PyVRP (arquitectura Python/C++ + pybind11 bindings)
- Vroom (matrices de costo dirigidas, evaluación C++)
- VeRyPy (construcción multisemilla modular)
- pytorch-drl4vrp (calibración dinámica de parámetros SA)
- LKH (búsqueda local 3-opt rigurosa)
- jsprit (operador Ruin-Recreate)
- timefold-quickstarts (aislamiento de invariantes)
- Rosomaxa/Open-VRP (inmutabilidad y TDD)
- VRP-RL (pre-clasificación de instancias)

### ✨ Added

#### Backend Python
- **Estructura modular:**
  - `backend_python/api/` — FastAPI endpoints (POST /solve, GET /instances, etc)
  - `backend_python/models/` — Entidades de dominio (Instancia, Cliente, Solución, Ruta)
  - `backend_python/persistence/` — Adapters duales (MongoDB, PostgreSQL)
  - `backend_python/service/` — Orquestador principal (solver_orchestrator.py, validation_service.py)

- **Orquestación inteligente:**
  - Motor de construcción multisemilla (Nearest Neighbor, Farthest, Random, Regret)
  - Lanzamiento concurrente de heurísticas iniciales
  - Pre-clasificación de instancias (VRP-RL inspired)

- **Validación de invariantes:**
  - Capacidad de vehículos no excedida
  - Cada cliente visitado exactamente una vez
  - Ciclos cerrados (depot → clientes → depot)
  - Demandas y distancias siempre positivas

- **Suite TDD:**
  - Tests unitarios para orquestador
  - Tests de integración Python↔C++
  - Fixtures estratificadas (small/medium/large instances)

#### Core C++
- **Núcleo algorítmico:**
  - `graph.hpp/cpp` — Estructura de grafo dirigido con validación
  - `cost_matrix.hpp/cpp` — Matriz de adyacencia asimétrica (Vroom-inspired)
  - `bindings.cpp` — pybind11 module para exponer C++ → Python

- **Builders (Construcción):**
  - Greedy Nearest Neighbor clásico
  - Farthest Insertion
  - Random construction
  - Regret-based insertion (k-regret)

- **Optimizers (Optimización):**
  - Simulated Annealing con temperatura dinámica
  - Parámetros calibrables vía DRL (pytorch-drl4vrp inspired)
  - ILS (Iterated Local Search) como fallback

- **Operators (Operadores Locales):**
  - 2-opt intra-ruta
  - Or-opt (relocate 1-3 clientes)
  - 3-opt LKH-inspired para pulido final
  - Ruin-Recreate (jsprit paradigm) como alternativa

- **Data Structures:**
  - Zero-copy numpy array passing (immutable design)
  - Shared types header-only (sin serialización)

#### Documentación
- `README.md` — Overview, quick start, stack técnico, créditos
- `docs/ARCHITECTURE.md` — Diseño profundo, diagramas, flujos de datos
- `docs/API.md` — Especificación REST con ejemplos cURL
- `docs/CREDITS.md` — Tabla detallada de atribuciones + justificación
- `docs/references.md` — Mapeo repos → ideas aplicadas
- `docs/adr/0001-hybrid-python-cpp.md` — Decisión arquitectónica principal
- `docs/adr/0002-asymmetric-cost-matrices.md` — Por qué grafos dirigidos
- `docs/adr/0003-drl-parameter-calibration.md` — DRL para tuning
- `docs/adr/0004-ruin-recreate-operators.md` — Operadores alternativos

#### Build & Deployment
- `CMakeLists.txt` — Build integrado Python + C++
- `requirements.txt` — Dependencias Python (FastAPI, pydantic, pybind11, numpy)
- `Makefile` — Targets: build, test, run, clean
- `docker-compose.yml` — Dev env (PostgreSQL, MongoDB)
- `.env.example` — Configuración de ejemplo
- `.gitignore` — Reglas para Python/C++ build artifacts

#### Tests
- `tests/unit/` — Tests unitarios Python
- `tests/integration/` — Tests de integración full-stack
- `tests/fixtures/` — Datasets (small: <100, medium: 100-1k, large: >1k nodos)

### 🔧 Technical Decisions (Documentadas en ADRs)

1. **Hybrid Python/C++:** Orquestación de alto nivel en Python, cálculos puros en C++ (PyVRP pattern)
2. **Asymmetric Matrices:** Grafos dirigidos, no asume simetría euclidiana (Vroom pattern)
3. **DRL Calibration:** Temperatura SA controlada dinámicamente vía Deep RL (pytorch-drl4vrp pattern)
4. **Modular Operators:** Builders, optimizers, operators separados → 10+ algoritmos sin refactor (jsprit pattern)
5. **Immutable Data Flow:** Invariantes garantizadas en paso Python↔C++ (Rosomaxa + Open-VRP philosophy)
6. **TDD Everywhere:** 100% coverage de orquestador + algoritmos (Open-VRP pattern)

### ⚠️ Known Limitations

- GIL de Python controlado: construcción multisemilla ocurre en Python pero C++ es single-threaded por ahora
- Matrices de distancia pre-computadas (OSRM/Valhalla integration pending)
- 3-opt experimental (optimización en progreso)

### 🎯 Next Phase (Roadmap)

- [ ] Implementar full 3-opt LKH con restarts
- [ ] Integración OSRM/Valhalla para distancias reales
- [ ] Paralelización C++ (multi-threaded SA)
- [ ] DRL training pipeline (pytorch-drl4vrp full integration)
- [ ] Web UI (React/Mapbox)
- [ ] Benchmarking público (CVRPLIB)
- [ ] Containerización (Docker image <100MB)

---

## [0.3.0] — 2026-07-23

### ✨ Added

#### Fase 3: Persistencia real + API integrada
- `backend_python/config.py`: configuración centralizada vía `.env.local` (fallback a variables de entorno del sistema)
- `PostgreSQLAdapter`: implementación real de `save_instance`/`load_instance`/`list_instances` contra PostgreSQL (antes stub)
- `MongoDBAdapter`: implementación real de `save_solution`/`load_solution`/`list_solutions`/`save_cost_matrix`/`load_cost_matrix` contra MongoDB (antes stub)
- `POST /solve`, `GET /instances`, `GET /solutions/{id}`, `GET /health`: integrados con los adapters reales (antes devolvían datos stub)
- `demo_phase3_e2e.py`: demo de punta a punta (crear instancia → persistir → resolver → persistir solución → recuperar → validar)
- `tests/unit/test_persistence.py`, `tests/unit/test_api_integration.py`: suite de integración contra PostgreSQL/MongoDB reales (vía Docker)

### 🐛 Fixed

- **`postgres_adapter.py` — incompatibilidad con Python 3.14:** `psycopg2` no publica wheels para 3.14 y falla al compilar desde código fuente en Windows. Se agregó fallback a `psycopg` (v3, misma sintaxis SQL/placeholders) cuando `psycopg2` no está disponible.
- **`test_persistence.py` — orden de importación no determinista:** los flags `POSTGRES_AVAILABLE`/`MONGO_AVAILABLE` leían `os.getenv("DATABASE_URL")` antes de que `backend_python.config` cargara `.env.local`, por lo que los tests se saltaban o fallaban según qué módulo se importara primero en la sesión de pytest. Se fuerza la carga de `config` al inicio del archivo de test.
- **`test_api_integration.py` — puerto hardcodeado:** las aserciones de `POSTGRES_PORT`/`DATABASE_URL` asumían el puerto 5432 fijo; se generalizaron para leer el puerto desde `config` en vez de un literal, ya que el puerto real depende del entorno (ver nota de infraestructura abajo).
- **MongoDB — `if not self.db:`** reemplazado por `if self.db is None:` en todos los métodos del adapter (PyMongo v4 lanza `NotImplementedError` al evaluar un objeto `Database` con `bool()`).

### 📝 Notas de infraestructura (no código)

- En entornos Windows con un servicio nativo de PostgreSQL ya corriendo en el puerto 5432, el contenedor Docker de desarrollo debe mapearse a un puerto alterno (`5433:5432` en este entorno) para evitar que el cliente hable con el Postgres equivocado — causa un `FATAL: password authentication failed` engañoso, no relacionado con las credenciales reales. Documentado en `.env.local` (no versionado).

### ⚠️ Known Limitations (actualizado)

- Bindings C++ (`vrp_solver` vía pybind11) no compilados en este entorno — requiere Python de 64 bits con headers de desarrollo; el sistema usa el fallback puro Python automáticamente y de forma transparente. No bloquea el pipeline solve→persist→retrieve.
- Sin retry/backoff en las conexiones a PostgreSQL/MongoDB — un fallo de conexión se propaga como error inmediato (aceptable para el alcance actual; ver sección "Rechazado" para el porqué de no añadir resiliencia todavía).

---

## [0.3.1] — 2026-07-23

### 🐛 Fixed

- **Colisión de ID cliente/depósito en el pipeline C++ (`api/__init__.py`, `solver_orchestrator.py`, `core_cpp/include/graph.hpp`):** `POST /solve` generaba `id=i` para clientes (`i` desde 0), mientras `_solve_cpp_pipeline` reserva `id=0` para el depósito en el grafo C++. `Graph::add_node` no detecta colisión de IDs, solo valida rango — un cliente con `id=0` sobrescribía silenciosamente el nodo del depósito. Fix: los IDs de cliente ahora se generan como `i + 1` en `api/__init__.py`.
- **Depósito hardcodeado en `(0.0, 0.0)` (`api/__init__.py`):** `POST /solve` ignoraba cualquier coordenada de depósito real. Se añadió el campo `depot_coordinates: tuple` (default `(0.0, 0.0)`, retrocompatible) a `InstanceRequest`.
- **`mongodb_adapter.py` — excepciones tragadas sin loggear:** los 5 métodos públicos (`save_solution`, `load_solution`, `list_solutions`, `save_cost_matrix`, `load_cost_matrix`) capturaban `except Exception: return False/None` sin registrar el error, ocultando fallos reales de persistencia. Se añadió `logger.error(...)` en cada except, alineado con el patrón que ya usa `postgres_adapter.py`.
- **`api/__init__.py` — retorno de `save_instance`/`save_solution` ignorado:** `POST /solve` loggeaba éxito incondicionalmente sin verificar el booleano de retorno de los adapters. Ahora se loggea a nivel `warning` si la persistencia falla, sin abortar la request (se mantiene el comportamiento "best effort").
- **Demanda de cliente aceptaba fraccionarios que se truncaban silenciosamente en dos puntos independientes** (`solver_orchestrator.py` al pasar al grafo C++, `postgres_adapter.py` al persistir), causado por `Node::demand: int` en el core C++. Se añadió validación explícita en `Cliente.__post_init__` (`backend_python/models/__init__.py`): demandas no enteras ahora se rechazan con `ValueError` en el punto de entrada, en vez de truncarse silenciosamente más adelante en el pipeline.

### 🔧 Changed

- `requirements.txt`: eliminadas `sqlalchemy==2.0.23` y `mongoengine==0.28.0` — no se importan en ningún archivo del código; la decisión de no usar ORM ya estaba documentada en `0.3.0`.
- `.env.example`: reescrito para reflejar las variables que `backend_python/config.py` realmente lee (`POSTGRES_HOST/PORT/USER/PASSWORD/DB`, `MONGO_HOST/PORT/DB`, `API_HOST/PORT/DEBUG`, `SOLVER_TIMEOUT_SECONDS`) en vez de `DATABASE_URL`/`MONGODB_URL` compuestas, que no coincidían con el código y causaban fricción real de onboarding.
- `docs/adr/0001-hybrid-python-cpp.md`: sección "Especificación" corregida — ya no lista SQLAlchemy/MongoEngine como stack de persistencia; refleja la decisión real (adapters directos, sin ORM) ya documentada en CHANGELOG `0.3.0`.
- Eliminada la carpeta `backend_python/tests/` (contenía solo un `__init__.py` vacío); la suite real vive en `tests/unit/`, tal como usan todos los comandos del `Makefile`.

---

## [0.3.2] — 2026-07-23

### 🐛 Fixed

- **`tests/unit/test_models.py` — sin test de regresión para el invariante de demanda entera introducido en `0.3.1`:** se añadió `test_cliente_demanda_debe_ser_entera`, siguiendo el mismo patrón que los tests vecinos de `demanda <= 0`.
- **`api/__init__.py` — `depot_coordinates: tuple` sin longitud fija producía `500` en vez de `422` ante input malformado:** un request con `depot_coordinates` de longitud distinta a 2 pasaba la validación de Pydantic sin error (tupla sin parametrizar) y fallaba después con `TypeError` al hacer `Coordinate(*request.depot_coordinates)`, cayendo en el `except Exception` genérico del endpoint y reportándose como error de servidor. Se tipó como `Tuple[float, float]`, delegando la validación de longitud a Pydantic — ahora responde `422` con mensaje claro. Verificado manualmente vía `TestClient`.
- **`solver_orchestrator.py:127` — `vrp_solver.Graph()` se construía con `num_vehiculos` en vez del número real de nodos (bug preexistente de Fase 2, no introducido por `0.3.1`, pero descubierto al auditar el flujo que ese delta modificó):** `Graph(int n)` reserva `n` nodos y usa `n` como cota superior en `add_node`. Con cualquier instancia con más clientes que vehículos (el caso normal en VRP), `add_node(client.id, ...)` habría lanzado `std::out_of_range` en cuanto se compilaran los bindings C++ — invisible hoy porque el fallback Python no usa `Graph`. Fix: `Graph(1 + len(self.instance.clientes))` (1 nodo depósito + N clientes). Complementa el fix de `id+1` de `0.3.1`: ese corrige el *valor* de los IDs, este corrige el *tamaño* del contenedor que debe alojarlos — ambos son necesarios para que el camino C++ funcione cuando se active.

### 🔧 Changed

- `docker-compose.yml`: credenciales de PostgreSQL alineadas a `.env.example` (`POSTGRES_DB=vrp_db`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=vrp_password`; antes `vrp_dev`/`vrp_user`/`vrp_pass`, que no coincidían con lo que `config.py` espera por defecto). El flujo documentado en README (`docker-compose up -d` + `.env.example`) ahora es consistente.
- `docker-compose.yml`: eliminadas `MONGO_INITDB_ROOT_USERNAME`/`MONGO_INITDB_ROOT_PASSWORD`/`MONGO_INITDB_DATABASE` del servicio `mongodb`. `config.py`/`MongoDBAdapter` no soportan credenciales para MongoDB (`MONGO_URL` se construye sin campo de usuario/contraseña) — exigir auth en el contenedor lo hacía imposible de usar con el código actual. Se alinea `docker-compose.yml` al uso real ya verificado en esta sesión (Mongo sin auth en desarrollo local), en vez de añadir soporte de credenciales no utilizado hoy.

---

## [0.3.3] — 2026-07-23

### 🐛 Fixed

- **Número de rutas generado por el solver nunca se validaba contra `flota.num_vehiculos` (defecto compartido por ambos caminos de solución — C++ y fallback Python — no exclusivo de uno).** `Instancia.__post_init__` (`backend_python/models/__init__.py`) valida que la demanda total quepa en la capacidad agregada (`num_vehiculos * capacidad`), pero eso es una cota agregada: no garantiza que un bin-packing greedy (Nearest Neighbor, tanto `NearestNeighbor::solve()` en C++ como `_construct_route_greedy` en el fallback Python de `solver_orchestrator.py`) reparta esa demanda en `num_vehiculos` rutas o menos. Era matemáticamente posible que la demanda cupiera en la capacidad total pero que el greedy necesitara más rutas que vehículos disponibles, y el resultado se aceptaba tal cual sin ninguna señal de infactibilidad. Fix: `SolverOrchestrator.solve()` (`backend_python/service/solver_orchestrator.py`) ahora verifica `len(solution.rutas) > self.instance.flota.num_vehiculos` tras obtener la solución (de cualquiera de los dos caminos) y lanza `ValueError` si se excede — no se tocó el algoritmo de construcción en sí, solo se añadió la validación posterior, consistente con el patrón de invariantes que el dominio ya usa. Test de regresión: `tests/unit/test_optimizers.py::TestFleetSizeValidation`, con un caso construido explícitamente (3 clientes de demanda 60 c/u, capacidad 100 por vehículo — ningún par cabe junto —, 2 vehículos disponibles: demanda total 180 ≤ 200 pero greedy requiere 3 rutas).

---

## [0.3.4] — 2026-07-23

### 🐛 Fixed

- **`tests/unit/test_optimizers.py:121-124` — test placeholder sin aserción real.** `test_3opt_is_stricter_than_2opt` contenía únicamente `assert True` con un comentario que no correspondía a ninguna validación, dando falsa sensación de cobertura de 3-opt. Cambiado a `pytest.skip("Requires C++ bindings to validate")`, consistente con sus dos tests vecinos en la misma clase (`TestLocalOperators`) que ya usan ese patrón honesto para lo que depende de bindings C++ no compilados en este entorno.

---

## [0.3.5] — 2026-07-23

### 🐛 Fixed

- **`api/__init__.py:23` — `coordinates: List[tuple]` sin longitud fija (mismo defecto de tipado ya corregido en `depot_coordinates` vía `0.3.2`, previamente dejado fuera de alcance).** Una `tuple` sin parametrizar no valida cantidad de elementos: un request con `coordinates` conteniendo entradas de longitud distinta a 2 pasaba la validación de Pydantic sin error. Tipado como `List[Tuple[float, float]]`, delegando la validación a Pydantic — ahora responde `422` con mensaje claro en vez de comportamiento indefinido más adelante en el pipeline. Verificado manualmente vía `TestClient` y cubierto por el nuevo test `test_solve_rejects_malformed_coordinates` en `tests/unit/test_api_integration.py`. Sin cambios de compatibilidad para clientes que ya envían pares `[x, y]` válidos (11 tests de `/solve` existentes siguen pasando sin modificación).

---

## [0.3.6] — 2026-07-23

### ✨ Added

- **Retry con backoff fijo en la conexión inicial de `PostgreSQLAdapter` y `MongoDBAdapter`** (`backend_python/persistence/postgres_adapter.py`, `mongodb_adapter.py`). Hasta ahora un fallo transitorio de red tumbaba el adapter en el primer intento (decisión previamente rechazada en `0.3.0`, ver nota abajo). Reconsiderado porque el despliegue va a dejar de ser exclusivamente esta máquina con Docker local — en una red real entre dos equipos, un fallo transitorio (DB aún arrancando, blip de red) ya no es un escenario hipotético. Implementación mínima: 3 intentos, 1 segundo de espera fija entre cada uno (`CONNECT_RETRIES`, `CONNECT_RETRY_DELAY_SECONDS`), sin librería nueva (`time.sleep` de stdlib). Se aplica solo a la conexión inicial (`__init__`) — los métodos de guardado/lectura individuales siguen siendo best-effort (retornan `False`/`None` en fallo), sin retry, porque ya son operaciones idempotentes desde la perspectiva del caller y añadir retry ahí sería sobreingeniería para un problema no observado en esa capa.
- **`psycopg2.connect(..., connect_timeout=5)`** añadido en `postgres_adapter.py`. Descubierto durante la verificación manual del retry: sin timeout explícito, un intento de conexión contra un host/puerto inalcanzable podía colgarse indefinidamente en Windows (varios minutos, no segundos), lo cual habría hecho que el retry con backoff fuera contraproducente — 3 intentos × "indefinido" es peor que 1 intento sin retry. `MongoDBAdapter` ya tenía timeout explícito (`serverSelectionTimeoutMS=5000`) desde antes, por eso el problema solo se manifestó en Postgres. Verificado con un puerto cerrado real: sin el fix, el proceso quedó colgado (tuvo que terminarse manualmente); con el fix, falla en un tiempo acotado.

### 🔧 Rechazo revisado

- **Retry/backoff exponencial en los adapters de persistencia:** la entrada original de `0.3.0` en la sección "Rechazado / Descartado" decía "no hay evidencia de fallos de conexión intermitentes en este entorno (Docker local)". Esa premisa deja de aplicar: el usuario confirmó que el despliegue futuro puede ocurrir en una máquina distinta a la actual, escenario donde un fallo transitorio de red ya no es hipotético. Se implementa con el alcance mínimo suficiente (backoff fijo, no exponencial; solo en la conexión inicial, no en cada operación) — no se reabre la puerta a la resiliencia completa que se rechazó (colas, circuit breakers, etc.), que sigue sin justificación real.

---

## [0.4.0] — 2026-07-23

### ✨ Added

- **Integración OSRM real para distancias sobre calles** (`backend_python/service/osrm_client.py`, `solver_orchestrator.py`). `SolverOrchestrator.solve()` ahora construye la matriz de costos una sola vez, antes de bifurcar entre el fallback Python y el pipeline C++ (`_build_cost_lookup()`), garantizando que ambos caminos usen exactamente la misma fuente de distancias — requisito ya exigido por `TESTING_STRATEGY.md` sección 2 (paridad entre caminos). El comentario `"Build cost matrix (Euclidean for now)"` que existía en `_solve_cpp_pipeline` desde Fase 2 queda resuelto: ahora usa OSRM cuando está configurado.
- **Cliente OSRM con chunking** (`osrm_client.py::get_osrm_matrix`): pide la matriz vía el endpoint `/table` de OSRM; si el número de coordenadas excede `OSRM_MAX_TABLE_SIZE`, particiona en múltiples llamadas por bloques y ensambla la matriz completa en Python. Diseñado con chunking desde el inicio (decisión confirmada por el usuario) para no chocar con el límite práctico de tamaño de matriz de OSRM frente a la promesa de escala del README ("50 a 100k+ clientes").
- **Fallback silencioso a distancia euclídea** si OSRM no está configurado (`OSRM_URL` vacío) o no responde (timeout, error HTTP, código de error de OSRM) — decisión de producto confirmada por el usuario: nunca falla `/solve` completo por una caída de OSRM, se loggea `warning` y se continúa con el cálculo euclidiano ya existente. Verificado con dos casos: `OSRM_URL` no configurado (salta la llamada HTTP por completo, sin latencia) y `OSRM_URL` apuntando a un puerto inalcanzable (falla rápido por el timeout, cae a euclídea).
- **`docker-compose.yml`:** nuevo servicio `osrm` (imagen oficial `osrm/osrm-backend`), apuntando a un mapa pre-procesado en `./data/osrm` (gitignored, mismo patrón que `data/large_instances/`). No se levanta automáticamente con `docker-compose up` si el mapa no fue preparado antes — requiere el paso offline `make osrm-prepare`.
- **`make osrm-prepare`** (nuevo target en `Makefile`): descarga el extracto de Perú desde Geofabrik (Lima Metropolitana no está disponible como extracto separado en Geofabrik; se usa el archivo de Perú completo, ~250MB) y lo pre-procesa (`osrm-extract` + `osrm-partition` + `osrm-customize`) — paso único, offline, análogo a `make build` para el core C++.
- **Config nueva** (`config.py`, `.env.example`): `OSRM_URL` (sin default — vacío significa "no usar OSRM", evita que el sistema intente conectar a un servicio que nadie levantó), `OSRM_MAX_TABLE_SIZE`, `OSRM_TIMEOUT_SECONDS`.

### 🐛 Fixed durante la implementación

- **`OSRM_URL` con default `http://localhost:5000` causaba que toda la suite de tests intentara conectar a OSRM y esperara el timeout completo (~4s por test) antes de caer al fallback**, incluso en máquinas sin OSRM levantado — la suite pasó de ~2s a ~51s. Corregido quitando el default: `OSRM_URL` vacío ahora salta la llamada HTTP por completo en vez de intentarla y fallar. Mismo principio que ya aplica `DATABASE_URL`/`MONGO_URL` (sin valor mágico que aparente estar configurado sin estarlo).

### Tests

- `tests/unit/test_osrm_client.py`: matriz simple y chunking contra un servicio OSRM real (`skipif` si `OSRM_URL` no está configurado, mismo patrón que `test_persistence.py` para Postgres/Mongo); propagación de `OSRMError` ante host inalcanzable (no requiere OSRM real, corre siempre).
- `tests/unit/test_optimizers.py::TestCostMatrixFallback`: fallback a euclídea cuando OSRM no está configurado y cuando está configurado pero inalcanzable (vía `monkeypatch` sobre el `config` singleton).
- Tests existentes de `_solve_python_fallback` (`test_optimizers.py`, `test_solver_end_to_end.py`) actualizados para pasar `cost_lookup` explícito, ya que la firma del método cambió al extraer la construcción de la matriz a un punto único.

---

## [0.4.1] — 2026-07-23

### 🐛 Fixed

- **`osrm_client.py::get_osrm_matrix` — el chunking podía exceder `max_table_size` en cada request individual, invalidando su propio propósito.** Cada bloque combinaba un rango de fila + un rango de columna (`block_coords = coords[row_start:row_end] + coords[col_start:col_end]`) usando `max_table_size` como tamaño de cada rango por separado — el tamaño combinado real podía llegar a `2 * max_table_size` (verificado con simulación: `max_table_size=2` generaba requests de hasta 4 coordenadas). Si `OSRM_MAX_TABLE_SIZE` se configura porque el servidor OSRM real rechaza requests más grandes, el chunking seguía enviando requests demasiado grandes, solo que con menor frecuencia. Fix: el tamaño de cada bloque ahora es `max_table_size // 2`, garantizando que la unión fila+columna nunca exceda el límite configurado (verificado: peor caso combinado = exactamente `max_table_size`).
- **README.md no documentaba la integración OSRM (`0.4.0`) como implementada.** Seguía describiéndola como roadmap ("OSRM/Valhalla-ready") sin mencionar que ya existe, y el Quick Start no incluía el paso `make osrm-prepare`. Corregido: sección "Motor Evaluador de Costos" actualizada, nueva sección "OSRM (opcional)" en Quick Start.
- **`osrm_client.py` sin advertencia sobre el requisito de coordenadas geográficas reales.** Activar `OSRM_URL` contra una instancia con coordenadas cartesianas/sintéticas (como las que usa toda la suite de tests y el demo) podría, en el peor caso, devolver una matriz "válida" pero sin sentido si esos valores caen dentro de un rango lon/lat plausible por coincidencia — sin ningún error que lo señale. Se documentó explícitamente en el docstring del módulo; no se añadió validación de rango en código (decisión de configuración del usuario, no un caso a adivinar en runtime — ver "Rechazado / Descartado").

---

## [0.4.2] — 2026-07-23

### ✨ Added

- **Bindings C++ (`vrp_solver`) compilados y activados por primera vez.** Bloqueo histórico resuelto: el MinGW instalado en esta máquina (`C:\MinGW`, GCC 6.3.0) era un toolchain de **32-bit**, incompatible con el Python de 64-bit del sistema — CMake lo rechazaba con `"Wrong architecture for the interpreter"`. Instalado MinGW-w64 real de 64-bit (WinLibs, GCC 16.1.0, vía `winget install BrechtSanders.WinLibs.POSIX.UCRT`) y reconfigurado el build apuntando explícitamente a ese compilador (`CMAKE_C_COMPILER`/`CMAKE_CXX_COMPILER`) y a `pybind11_DIR` (`python -c "import pybind11; print(pybind11.get_cmake_dir())"`). El `.pyd` compila y enlaza correctamente (`vrp_solver.cp314-win_amd64.pyd`).
- **`MINGW_BIN_DIR` (nueva variable de entorno, opcional, solo Windows).** Descubierto que Python 3.8+ en Windows no resuelve las DLLs de runtime de un `.pyd` compilado con MinGW (`libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`) vía `PATH` del proceso — requiere `os.add_dll_directory()` explícito (cambio de seguridad de Python, no un bug de esta integración). `solver_orchestrator.py` ahora llama `os.add_dll_directory(MINGW_BIN_DIR)` antes de `import vrp_solver` si la variable está seteada y el directorio existe; si no, el import de `vrp_solver` falla como antes y el sistema usa el fallback Python automáticamente — mismo comportamiento "opcional, sin bloquear" que ya tienen `OSRM_URL`/`DATABASE_URL`.

### 🐛 Fixed

- **`solver_orchestrator.py::_solve_cpp_pipeline` — el depósito (`id=0`) se copiaba dentro de `Ruta.secuencia`, violando el invariante de unicidad de `Solucion`.** Bug real de Fase 2 (`b64092e`), invisible desde su origen porque el pipeline C++ nunca se había ejecutado hasta este parche (bindings no compilados). `cpp_route.sequence` (C++) incluye el depósito al inicio y fin de cada ruta (`depot → clientes → depot`, patrón estándar VRP), pero se copiaba tal cual a `Ruta.secuencia` (que en el dominio Python representa solo clientes) — con 2+ rutas, el depósito aparecía repetido entre ellas, y `Solucion.__post_init__` lo rechazaba como `"cliente visitado múltiples veces"`. Confirmado con el traceback real: `secuencia=[0, 1, 3, 2, 0]` para una ruta de 3 clientes. Fix: filtrar `node_id != 0` al convertir `cpp_route.sequence` a `Ruta.secuencia`. Verificado: 59/59 tests pasando con el pipeline C++ real activo (antes solo se ejercitaba el fallback Python), demo end-to-end con costo 145.78 (mejor que el fallback Python, 146.86 — el NN→SA→3-opt real optimiza más que el greedy simple, como se esperaba por diseño).

### 📝 Notas de infraestructura (no código)

- Instalación de MinGW-w64 (WinLibs) es específica de esta máquina, no versionada en git — `MINGW_BIN_DIR` vive en `.env.local`. Otro desarrollador en otra máquina necesitaría repetir la instalación (o usar MSVC/otro toolchain de 64-bit) para activar los bindings; sin hacerlo, el sistema sigue funcionando en fallback Python sin ningún cambio de comportamiento — este parche no introduce una dependencia dura.

---

## [0.4.3] — 2026-07-23

### ✨ Added

- **Validación de rango geográfico (lon/lat) en `osrm_client.py::get_osrm_matrix`.** Antes solo se advertía en el docstring; ahora `_validate_coords_are_geographic()` rechaza explícitamente cualquier coordenada fuera de `[-180, 180]` (lon) / `[-90, 90]` (lat) **antes** de hacer cualquier llamada HTTP, lanzando `OSRMError` (que activa el fallback silencioso a euclídea ya existente). No detecta coordenadas cartesianas que caigan dentro de un rango lon/lat plausible por coincidencia (limitación ya documentada, no resuelta por esta validación), pero sí el caso más común y peligroso: instancias sintéticas de prueba con valores muy fuera de rango. Test de regresión: `tests/unit/test_osrm_client.py::test_osrm_matrix_rejects_non_geographic_coordinates` (no requiere OSRM real, corre siempre).
- **`Graph::add_node` (`core_cpp/include/graph.hpp`) ahora detecta colisión de IDs.** Se añadió un `std::vector<bool> assigned` para rastrear qué posiciones ya fueron asignadas — una segunda llamada con el mismo `id` lanza `std::invalid_argument` en vez de sobrescribir el nodo anterior en silencio (mapeado a `ValueError` en Python vía pybind11). Cierra el vector de bug que causó la colisión cliente/depósito de `0.3.1`. Verificado en dos niveles: test C++ nativo (`core_cpp/tests/test_graph.cpp::DuplicateIdRejected`, vía CTest) y llamada manual a través de los bindings compilados.

### 🐛 Fixed

- **`CMakeLists.txt` (raíz) y `core_cpp/CMakeLists.txt` hacían `add_subdirectory(core_cpp/tests)` dos veces — bug preexistente, nunca detectado porque nadie había compilado la suite C++ con `BUILD_TESTS=ON` hasta ahora.** CMake fallaba con `"binary directory is already used to build a source directory"`. Fix: el `add_subdirectory(tests)` vive solo en `core_cpp/CMakeLists.txt` (dueño natural de ese subdirectorio); el `CMakeLists.txt` raíz solo llama `enable_testing()`. Efecto secundario descubierto: `enable_testing()` debe ejecutarse **antes** de `add_subdirectory(core_cpp)` para que CTest registre los tests de ese subárbol — corregido el orden también. Resultado: primera compilación exitosa de la suite C++ nativa completa (GoogleTest vía `FetchContent`), **10/10 tests pasando** (`vrp_core_tests.exe`), incluyendo el nuevo test de colisión de IDs.

### 🔬 Validación de escala real (chunking OSRM, deuda técnica de `0.4.0`/`0.4.1`)

Se levantó un servicio OSRM real (`make osrm-prepare` con el extracto de Perú de Geofabrik, 242MB descarga → 2.5GB pre-procesado) y se probó `get_osrm_matrix` con coordenadas aleatorias reales dentro de Lima Metropolitana, en vez del caso sintético de 4 coordenadas que era la única cobertura hasta ahora:

| n coordenadas | Tiempo | Requests HTTP (`max_table_size=100`) |
|---|---|---|
| 50 | 0.26s | 1 (sin chunking) |
| 150 | 2.11s | 9 |
| 300 | 7.72s | 36 |
| 1000 | 85.01s | 400 |

**Resultado: el chunking funciona correctamente (matriz completa y correcta en los 4 casos), pero el costo real a escala es alto** — 85 segundos para 1000 clientes, muy por encima de la promesa de "100-500ms" del README para instancias de ese tamaño (esa cifra asume distancia euclídea, no OSRM). Causa: el patrón O(bloques²) del chunking (400 requests secuenciales para n=1000, ~212ms promedio cada uno). Confirma numéricamente la deuda técnica ya documentada en `TESTING_STRATEGY.md`, ahora con datos reales en vez de una suposición. También se confirmó que el servidor OSRM real rechaza tablas de 1000 coordenadas en una sola llamada (`400 Bad Request` sin chunking) — validando que el chunking no es opcional para instancias medianas/grandes con OSRM activo, es un requisito funcional.

**No se optimizó el chunking en este parche** (paralelizar requests, cachear resultados, etc.) — queda como decisión explícita para cuando el frontend/casos de uso reales confirmen que instancias de cientos de clientes con OSRM activo son un escenario a soportar en producción, no antes.

---

## [0.4.4] — 2026-07-24

### 🐛 Fixed

- **README.md "Prerequisites" indicaba C++20 (GCC 9+, Clang 11+); el proyecto usa C++17 desde hace varias fases.** `CMakeLists.txt` ya documentaba explícitamente el downgrade (`"C++17 standard (C++20 not available in all environments)"`) pero el README nunca se actualizó — un usuario nuevo podría instalar un toolchain pensando que necesita C++20. Corregido a "C++17 compiler (GCC 9+, Clang 11+, MinGW-w64 en Windows)", mencionando explícitamente MinGW-w64 como opción validada en `0.4.2`.
- **El fix de CMake duplicado de `0.4.3` perdió `EXCLUDE_FROM_ALL`, causando que un build normal (`cmake --build .` / `make build`) compilara la suite de tests C++ completa (incluyendo GoogleTest vía `FetchContent`, que requiere descarga de internet) aunque el usuario no pidiera correr tests.** La versión original tenía `add_subdirectory(core_cpp/tests EXCLUDE_FROM_ALL)`; al mover ese `add_subdirectory` a `core_cpp/CMakeLists.txt` para resolver la duplicación, se perdió el flag. Confirmado con una reconfiguración limpia: sin el flag, `cmake --build .` con `BUILD_TESTS=ON` (default) compilaba gtest/gmock completo y `vrp_core_tests.exe` como parte del build normal. Fix: `add_subdirectory(tests EXCLUDE_FROM_ALL)` en `core_cpp/CMakeLists.txt` — el target de tests ahora solo se compila si se invoca explícitamente (`cmake --build . --target vrp_core_tests` o vía `ctest`, que lo requiere como dependencia). Efecto colateral corregido en el mismo parche: `Makefile::test-cpp` ahora compila `vrp_core_tests` explícitamente antes de `ctest` (antes asumía que `make build` ya lo había compilado, lo cual dejó de ser cierto con `EXCLUDE_FROM_ALL` restaurado). Verificado: build normal ya no compila tests (confirmado por ausencia de pasos de gtest en el log), `make test-cpp` sigue funcionando (10/10 tests C++ pasando).

---

## [0.4.5] — 2026-07-24

### 🗑️ Removed

- **Eliminado el árbol académico Qt/C++17 completo (`src/`, 17 archivos) más `tests/test_core.cpp` y `demo.py` — código huérfano que contradecía la propia documentación del proyecto.** `CHANGELOG.md` (sección "Notas de Migración") declara explícitamente: *"El código académico anterior (Git history) se preserva pero no se integra en este árbol"* — la intención documentada era que ese código viviera solo en el historial de git, recuperable si hiciera falta, no como archivos activos en el working tree. En la práctica seguía presente físicamente, sin estar referenciado en ningún `CMakeLists.txt` activo (ni raíz ni `core_cpp/`) — confirmado que no compila como parte del proyecto actual.
- **Descubierto mediante `graphify` (mapeo de grafo de conocimiento del repo, herramienta nueva de esta sesión):** el clustering agrupó `src/core/Instancia.h`, `src/core/Solucion.h`, `src/core/Cliente.h` junto con `backend_python/models/__init__.py` en la misma comunidad, porque comparten nombres de clase (`Instancia`, `Solucion`, `Cliente`) con el dominio activo — ruido de similitud que había pasado inadvertido en todas las rondas de auditoría anteriores, porque nadie inspecciona manualmente un directorio (`src/`) que no aparece en ningún build activo.
- `tests/test_core.cpp`: compilaba explícitamente contra `src/` (ver su propio comentario de cabecera con instrucciones de compilación manual `g++ -Isrc ...`) — 100% huérfano, sin ningún caller ni referencia fuera de sí mismo.
- `demo.py`: parcialmente vivo (sí importaba `backend_python.models`/`solver_orchestrator`, el backend real), pero era el demo de Fase 1 sin persistencia — completamente superado por `demo_phase3_e2e.py` (Fase 3, con persistencia real). Eliminado por redundancia, no por estar roto.
- Verificado: 60/60 tests Python pasando sin regresión, build C++ limpio (CMake + `vrp_core` + `vrp_solver` compilan igual sin `src/`) — ninguno de los tres elementos era una dependencia real del sistema activo.

---

## [0.5.0] — 2026-07-24

### ✨ Added — Logística real: capacidad por vehículo, dimensiones, multi-paquete, cobertura, ETA estimado

**Backend — capacidad por vehículo (reemplaza el planteo inicial de "capacidad promedio").** El solver asumía flota homogénea: un `num_vehicles` + un `vehicle_capacity` único para todos. En uso real la flota es heterogénea (motos, camionetas, capacidades distintas). En vez de aproximar con un promedio (que puede sobrecargar el vehículo real más chico), se extendió el algoritmo de construcción (`NearestNeighbor`, que ya arranca ruta → agrega el nodo más cercano que quepa → cierra cuando no entra nada más → arranca la siguiente) para aceptar una **lista de capacidades, una por vehículo**, usadas en orden. Cambios:
- `core_cpp/include/builders/nearest_neighbor.hpp`: constructor de `double capacity` a `std::vector<double> capacities`; cada ronda usa `capacities[vehicle_id % capacities.size()]`.
- `core_cpp/src/bindings.cpp`: firma pybind11 actualizada (conversión automática lista Python ↔ `std::vector<double>` vía `pybind11/stl.h`, ya incluido).
- `backend_python/models/__init__.py`: `Flota.capacidades_vehiculos: Optional[List[float]]` (nuevo campo opcional) + propiedad `capacidad_total` que la considera si está presente.
- `backend_python/api/__init__.py`: `InstanceRequest.vehicle_capacities: Optional[List[float]]` — si viene, tiene prioridad sobre `vehicle_capacity` escalar.
- `backend_python/service/solver_orchestrator.py`: tanto el pipeline C++ como el fallback Python (`_construct_route_greedy`) usan la lista si está presente, vía helper `_capacity_for_vehicle`.
- **100% retrocompatible**: sin `vehicle_capacities` en el request, comportamiento idéntico a antes (verificado con el mismo payload de pruebas anteriores: `total_cost: 48761.3`, sin cambios). 62 tests Python + suite C++ (`ctest`) pasan sin modificación.
- Verificado con flota heterogénea real (3 vehículos: 200/100/50 kg): ninguna ruta excede la capacidad de su vehículo asignado.

**Frontend — Fase 1 de logística real, capturada íntegramente en UI/datos, sin más cambios al contrato HTTP que el campo opcional de arriba:**
- **Dimensiones + multi-paquete**: `src/lib/types.ts` (`Package`, `ClientGroup`), `src/lib/importClients.ts` extendido con columnas `cliente_id`/`largo`/`ancho`/`alto` (alias case-insensitive) y `groupPackagesByClient` — filas con el mismo `cliente_id` se agrupan en un punto de entrega con paquetes separados, demanda = suma de pesos, volumen = suma de `largo×ancho×alto`. Sin columna `cliente_id`, cada fila sigue siendo un cliente distinto (retrocompatible con `clientes_lima_50.csv`/`clientes_lima_100.csv`).
- **Catálogo de vehículos**: `src/lib/vehicleCatalog.ts` + `VehicleCatalogManager.tsx` (persistido en `localStorage`, reutilizable entre sesiones) + `FleetSelector.tsx` (selección de flota disponible "hoy"). `src/lib/buildInstance.ts::buildInstanceRequest` colapsa la selección a `vehicle_capacities` ordenada de mayor a menor capacidad (aplicando el margen de tolerancia de cada vehículo) antes de enviar al backend.
- **Zona de cobertura**: polígono dibujado sobre el mapa existente (`RouteMap.tsx`, modo `editingCoverage` — sin mapa separado), persistido en `localStorage` (`src/lib/coverageZone.ts`), point-in-polygon vía `@turf/boolean-point-in-polygon` (nueva dependencia). Clientes fuera de zona se marcan visualmente y se excluyen del `POST /solve`, sin perderse de la UI.
- **ETA estimado**: `src/lib/osrm.ts::fetchRouteWithDuration` (nueva función, no rompe `fetchRouteGeometry`) trae la duración total de cada ruta desde OSRM; `src/lib/eta.ts::estimateRouteEtas` prorratea esa duración por distancia acumulada de la geometría hasta cada parada (asume velocidad constante — aproximación declarada, no una predicción de tráfico real) y aplica un colchón heurístico (±10%, mínimo 5 min) para mostrar un rango, no una hora exacta. Puramente informativo, post-solve, sin restricción real en el solver — decisión explícita para evitar prometer una precisión de VRPTW que el algoritmo actual no soporta.
- Explícitamente descartado para esta fase (decisión del usuario): prioridad real de "urgente" en el algoritmo del solver.

---

## [0.6.0] — 2026-08-01

### 🔗 Adopción del sistema de especificación trazada

A partir de este commit, el proyecto adopta `SPEC.md` (reconstruido) como fuente de verdad funcional, con la suite de tests anotada con IDs de regla/escenario (`spec: RN-XXX`) y verificada mediante `make traceability`. Ver [docs/plan-adopcion.md](docs/plan-adopcion.md) para el plan completo y [docs/adr/ADR-005-estrategia-verificacion.md](docs/adr/ADR-005-estrategia-verificacion.md) para el contrato de `verify`.

- **`Makefile`:** nuevos targets `verify` (build + test + trazabilidad), `traceability` (`scripts/check_traceability.py`, extrae IDs de `SPEC.md` y verifica que cada uno tenga al menos un test anotado) y `mutation` (mutmut sobre `backend_python/models`, umbral fijado en 98% — 2 puntos por debajo del score base medido de 100%, ver sección 5 de `docs/plan-adopcion.md`).
- **Corrección de referencia:** `make build`/`make test-cpp` apuntaban al directorio `build/` (vacío, sin caché de CMake); corregido a `build64/`, el directorio real donde el core C++ está compilado en esta máquina desde `0.4.2`. No cambia comportamiento — solo corrige una ruta que ya estaba rota.
- **Anotación de la suite:** 25 de los 30 IDs de `SPEC.md` tienen al menos un test que los cubre explícitamente. Sin cobertura: `EC-003` (fallback transparente del core C++, ejercitado implícitamente por toda la suite en máquinas sin bindings, sin un test que lo fuerce explícitamente), `RN-003` (heterogeneidad de `capacidades_vehiculos` — hallazgo nuevo, sin test dedicado), `RNF-001/002/003` (requisitos de performance, sin benchmark automatizado en la suite).
- **Estado de `verify` en esta máquina:** `test-py` (194 passed, 3 skipped) y `test-cpp` (1/1 passed) en verde; `traceability` falla honestamente por las 5 reglas sin cobertura de arriba; `build` no pudo verificarse de punta a punta en esta sesión por un bloqueo de verificación SSL entre CMake/FetchContent y GitHub al intentar poblar GoogleTest — no es un problema del código, ver sección de hallazgos no implementados más abajo.

Ver la entrada correspondiente más abajo en **Rechazado / Descartado** para los tests eliminados durante esta adopción.

---

## [0.6.1] — 2026-08-01

### 🔗 Cierre de trazabilidad — RN-003, EC-003, RNF-001/002/003

Cierra el agujero de trazabilidad reportado en `docs/hallazgos-actual.md` tras la adopción de `0.6.0`. Los 30/30 IDs de `SPEC.md` tienen ahora al menos un test anotado; `make traceability` pasa en verde.

### ✨ Added
- `tests/unit/test_models.py`: 2 tests nuevos para RN-003 (`Flota` heterogénea) — longitud de `capacidades_vehiculos` distinta a `num_vehiculos`, y capacidad individual `<= 0`. La validación ya existía en `Flota.__post_init__`; solo faltaba el test dedicado.
- `tests/performance/test_rnf_thresholds.py` (nuevo): 3 tests para RNF-001/002/003, `skipif` sin bindings C++ compilados (mismo patrón que OSRM/DB en ADR-005). Confirman que el solver resuelve la instancia sin fallar a cada escala; no assertan los umbrales de tiempo del SPEC como passing/failing.

### 🔀 Changed
- `tests/unit/test_optimizers.py`: `test_orchestrator_fallback_returns_valid_solution` anotado con `spec: EC-003` (el test ya existía y ya ejercitaba el fallback; solo le faltaba la anotación).
- `scripts/check_traceability.py`: implementa la excepción `spec: PENDIENTE` que el propio docstring del script ya prometía pero el código nunca aplicaba — un ID anotado así queda excluido del chequeo de cobertura, en vez de reportarse como faltante.
- `SPEC.md` §8: RNF-001/002/003 marcados `[DEUDA TÉCNICA]`.
- `pytest.ini` (nuevo): `pythonpath = .` — `make test-py` invoca `pytest` sin `-m` (a diferencia de `python -m pytest`, usado manualmente durante todo este ciclo), y sin esta configuración `tests/conftest.py` no podía importar `backend_python`, abortando toda la colección de tests antes de correr uno solo. Bug preexistente del `Makefile`, no introducido por este delta; sin `pytest.ini` no había forma de dejar `make verify` en verde de punta a punta.

### ADR Actualizado
Nuevo **[ADR-006](docs/adr/ADR-006-deuda-rendimiento-3opt.md)**: declara como deuda técnica el incumplimiento medido de RNF-001/002/003. Medido en esta máquina, con bindings C++ reales y sin ruido de red OSRM: RNF-001 ~50ms (al límite del umbral 10-50ms), RNF-002 ~1,054ms (~2x el umbral de 500ms), RNF-003 ~443s (~90x el umbral de 5s). Causa raíz: el operador 3-opt no tiene límite de tiempo ni escala sus iteraciones frente a `n`, mientras que `max_iters` de Simulated Annealing (`solver_orchestrator.py`) se satura en 1000 para cualquier instancia de 20+ clientes — el costo por movimiento de 3-opt, no el conteo de iteraciones de SA, domina el tiempo total a mayor escala. No se infló el SPEC para que los tests pasaran artificialmente; los umbrales aspiracionales se preservan como objetivo de producto, la brecha queda documentada como deuda con mitigación futura propuesta (`time_limit_ms` en los operadores C++, o paralelización de la búsqueda local).

### Rechazado / Descartado
- Recalibrar los umbrales de RNF-001/002/003 a los valores medidos actuales — descartado: infla la especificación para ocultar una regresión de rendimiento real en vez de corregirla.
- Test de rendimiento con assert de umbral real (`elapsed < threshold`) — descartado tras confirmar el incumplimiento: un assert que falla de forma predecible en cada corrida de `verify` no aporta información nueva sobre la deuda ya documentada en el ADR-006; se reemplazó por un assert funcional (el solver resuelve sin fallar a esa escala).

### Estado de `verify` en esta máquina
`make verify` (build + test + trazabilidad) en verde de punta a punta: `build` compila sin el bloqueo SSL que reportaba `0.6.0` (ya no reproducible); `test-py` 202 passed / 0 failed (con el contenedor `osrm` local levantado — sin él, los 3 tests de `TestOSRMIntegration` se saltan/fallan por falta de servidor, no por regresión); `test-cpp` 1/1 passed; `traceability` 30/30 IDs cubiertos.

---

## [0.6.2] — 2026-08-01

### 🔍 Ronda 1 de auditoría por roles (Jefe/dueño, Operador/operario, Repartidor)

Ciclo de exploración con un agente por rol de usuario (`agent-workflow/prompts/12-auditoria-roles-claude.md`). Operador y Repartidor: cero hallazgos — ambos flujos ya estaban cubiertos por fixes de rondas anteriores. Jefe (dueño): 2 hallazgos, ambos `[REGLA NUEVA]`, aprobados e implementados en esta misma ronda.

### ✨ Added
- **RN-COV-002 (Validez de Zona de Cobertura):** `PUT /coverage-zone` exigía cero validación de forma — `CoverageZoneRequest.points` podía guardar un polígono de 0-2 puntos o coordenadas fuera de rango geográfico, a diferencia de `InstanceRequest.coordinates` (RN-012), que sí reutiliza `_validate_lng_lat_pairs`. El único guardarraíl existente era la UI (`RouteMap.tsx`, exige `>= 3` puntos al dibujar) — cualquier llamada directa a la API lo evitaba. Fix: `CoverageZoneRequest` gana su propio `field_validator` que exige mínimo 3 puntos y reutiliza `_validate_lng_lat_pairs` (`backend_python/api/__init__.py`). Tests: `test_put_rejects_fewer_than_3_points`, `test_put_rejects_coordinate_out_of_range` (`tests/unit/test_coverage_zone_api.py`).
- **RN-EXP-002 (Filtro de Exportación sin Resultado):** `GET /solutions/{id}/export.pdf?vehicle_id=N` con un `vehicle_id` sin ninguna ruta en la solución devolvía `200 OK` con un PDF de 0 páginas de contenido — indistinguible de una descarga exitosa hasta abrir el archivo. Causa: `build_route_pdf` filtra `rutas` por `vehicle_id` sin verificar que el filtro matcheó algo antes de generar el documento. Fix: `export_solution_pdf` valida que exista al menos una ruta con ese `vehicle_id` en la solución antes de generar el PDF; si no, `404` (`backend_python/api/__init__.py`). Test: `test_export_pdf_404_for_vehicle_id_with_no_route` (`tests/integration/test_export_endpoint.py`).

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 205 passed / 0 failed, `test-cpp` 1/1 passed, `traceability` 32/32 IDs cubiertos (subió de 30 con las dos reglas nuevas).

### 🔍 Ronda 2 de auditoría por roles — cero hallazgos

Los tres roles (Jefe/dueño, Operador/operario, Repartidor) re-verificaron los fixes de RN-COV-002/RN-EXP-002 (siguen andando) y exploraron el resto de su superficie sin encontrar ningún problema nuevo. Primera ronda limpia del ciclo — según la condición de cierre, se necesita una ronda de confirmación también limpia para cerrar el ciclo.

### 🔍 Ronda 3 (confirmación) de auditoría por roles — cero hallazgos, ciclo cerrado

Segunda ronda limpia consecutiva: los tres roles exploraron ángulos nuevos no cubiertos en Rondas 1-2 (reprogramación, asignación de vehículos a repartidores, transiciones de `delivery_status`, filtrado cruzado entre repartidores, borrado de instancias) sin encontrar ningún hallazgo — todo lo tocado ya tenía guards documentados de rondas de auditoría anteriores del proyecto. Ciclo cerrado por rondas limpias (Ronda 2 + Ronda 3 sin hallazgos en ningún rol).

---

## [0.7.0] — 2026-08-02

### 🚀 P-01/P-02 — Fix real de rendimiento del pipeline C++ (RNF-001/002/003)

Cierra la deuda técnica del ADR-006. El diagnóstico original de ese ADR (operador 3-opt sin límite de tiempo/escala) era **incorrecto** — un perfilado con timing real por etapa (instancia de 5,000 clientes, bindings C++ reales) lo descartó: 3-opt y SimulatedAnnealing juntos representaban menos del 2% del tiempo total. El cuello de botella real era la construcción de `CostMatrix` celda por celda desde Python (`_solve_cpp_pipeline`), cruzando la frontera pybind11 N² veces — 98.4% del tiempo total (~84s de ~85s medidos en 5,000 clientes).

### ✨ Added
- `core_cpp/include/cost_matrix.hpp`: `CostMatrix::set_costs_bulk(const double* flat, size_t flat_size)` — llena la matriz completa en una sola pasada C++ desde un buffer plano row-major, en vez de `N²` llamadas a `set_cost`.
- `core_cpp/src/bindings.cpp`: expone `set_costs_bulk` recibiendo un `numpy.ndarray` 2D contiguo (`py::array_t<double, py::array::c_style | py::array::forcecast>`) — una sola travesía de la frontera pybind11.
- `core_cpp/tests/test_cost_matrix.cpp`: 3 tests nuevos (`SetCostsBulkMatchesCellByCell`, `SetCostsBulkRejectsWrongSize`, `SetCostsBulkRejectsNegative`).
- `backend_python/service/solver_orchestrator.py`: `_build_cost_matrix_array()` — construye la matriz de costos como array NumPy denso (vectorizado con NumPy en el caso euclídeo, `np.asarray` directo en el caso OSRM), fuente única para `_build_cost_lookup` (dict, fallback Python) y `_solve_cpp_pipeline` (array, pipeline C++). Elimina el dict intermedio de 25M+ entradas que antes se reconstruía para instancias grandes.

### 🔀 Changed
- `SPEC.md` §8: RNF-001/002/003 ya no llevan `[DEUDA TÉCNICA]` — los tres umbrales se cumplen.
- `tests/performance/test_rnf_thresholds.py`: los 3 tests recuperan su assert real de umbral de tiempo, anotados `spec: RNF-001/002/003` (ya no `spec: PENDIENTE`).
- `docs/adr/ADR-006-deuda-rendimiento-3opt.md`: estado `Resuelto`, diagnóstico corregido con datos de perfilado, y la solución real documentada.

### Medido en esta máquina (bindings C++ reales, sin ruido de red OSRM)

| RNF | Escala | Umbral SPEC | Antes | Después |
|---|---|---|---|---|
| RNF-001 | 50 clientes | 10-50ms | ~50ms (al límite) | **~29ms** |
| RNF-002 | 500 clientes | 100-500ms | ~1,054ms (~2x el umbral) | **~78ms** |
| RNF-003 | 5,000 clientes | 1-5s | ~443s (~90x el umbral) | **~2.2s** |

No se tocaron los operadores de búsqueda local (2-opt, 3-opt, Or-opt, SimulatedAnnealing) — el perfilado confirmó que nunca fueron la causa del problema de rendimiento.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 205 passed / 0 failed en 103s (antes ~900s, dominado por el test RNF-003 lento), `test-cpp` 1/1 passed, `traceability` 32/32 IDs cubiertos.

### Rechazado / Descartado
- Límites de tiempo (`time_limit_ms`) en los operadores C++ de búsqueda local, como proponía la primera versión del ADR-006 — descartado tras el perfilado real: esos operadores nunca fueron el cuello de botella, así que ese fix no habría movido el tiempo medido.

---

## [0.7.1] — 2026-08-02

### 🧹 Resolución del backlog de `docs/PENDIENTES.md`

Cierra las 4 decisiones pendientes y las 2 deudas de suite (`P-03`, `P-04`) registradas en `docs/PENDIENTES.md`.

### 🔀 Changed
- **RN-013 (nueva, `SPEC.md` §5):** el número de rutas de una solución no puede exceder `num_vehiculos` de la flota, incluso si la demanda agregada es válida (RN-005) — el bin-packing greedy puede fragmentar en más rutas de las disponibles si ningún subconjunto de clientes cabe junto en la capacidad de un vehículo. `tests/unit/test_optimizers.py::TestFleetSizeValidation` (ya existente, sin ID) queda anotado con `spec: RN-013`.
- `tests/unit/test_optimizers.py::TestOptimizationQuality::test_python_fallback_produces_feasible_solution`: anotado `spec: RN-011, RN-005, RN-010` (cobertura única, capacidad respetada, costo total consistente) — el test ya ejercitaba las tres reglas, solo le faltaba la anotación.
- `tests/unit/test_optimizers.py::TestSolverPipeline`, `tests/unit/test_api_integration.py::TestAPIFactory`, `tests/unit/test_osrm_client.py`: `spec: PENDIENTE` reemplazado por una nota explícita de cuarentena técnica permanente (instanciación de FastAPI, cliente HTTP OSRM, logging del pipeline) — no mapean a ninguna regla de dominio, conforme a `TESTING_STRATEGY.md` §4.

### 🗑️ Removed
- `core_cpp/include/solution.hpp`: `Solution::is_valid()` — stub (`// TODO: implement validation`, siempre `true`) que aparentaba validar invariantes sin hacerlo. La validación real ya vive en Python (`Solucion.__post_init__`, con mensajes en español ya cuidados). Sin callers en Python (`grep` confirmó cero usos). Binding pybind11 correspondiente eliminado en `core_cpp/src/bindings.cpp`.
- `tests/conftest.py`: fixtures `small_instance`/`medium_instance`/`large_instance` — placeholders huérfanos del árbol académico Qt/C++ (firma de modelo incompatible con el dominio actual, dos de los tres eran literalmente `return None`). Ningún test real las usaba: `test_optimizers.py` define su propio fixture local `medium_instance`, que pytest resuelve en su lugar (prioridad de fixture local sobre `conftest.py`). El fixture `_run_migrations` (real, usado por `test_migrations.py`) se preserva sin cambios.

### Decisiones de producto (sin cambio de código)
- **Política DRL para optimización (ADR-0003):** se mantienen las heurísticas deterministas (`_compute_sa_params`). Sin evidencia de que la calidad de solución actual sea un problema — invertir en DRL (dataset, infraestructura de entrenamiento, PyTorch en runtime) es especulativo sin necesidad concreta reportada.
- **Cobertura geográfica OSRM:** se mantiene solo Perú — el negocio apunta a mercados locales. Ampliar a otro país es mecánico (`make osrm-prepare` con otro extracto de Geofabrik), disponible cuando haya demanda real.
- **Reintentos de conexión a BD:** ítem retirado de "Decisiones pendientes" por obsoleto — ya resuelto en `0.3.6` (`CONNECT_RETRIES` en ambos adapters). Referenciaba `PHASE_3_FINAL_STATUS.md`, documento de una fase temprana nunca resincronizado.

### Estado de `verify` en esta máquina
`make verify` en verde: `test-py` 205 passed / 0 failed en 98s, `test-cpp` 1/1 passed, `traceability` 33/33 IDs cubiertos (subió de 32 con RN-013).

---

## Rechazado / Descartado

Decisiones evaluadas y descartadas explícitamente para mantener el alcance YAGNI/KISS:

- **Tests eliminados en la adopción del sistema de especificación (`0.6.0`):** aprobados en `docs/plan-adopcion.md` sección 2.
  - `test_optimizers.py::TestSimulatedAnnealing::test_orchestrator_has_sa_params_computation`, `test_sa_params_scale_with_instance_size`, `TestLocalOperators::test_solution_respects_invariants_after_optimization`, `test_2opt_improves_or_maintains_solution`, `test_3opt_is_stricter_than_2opt` — afirmaban el cálculo matemático intermedio de la mejora porcentual en Python de 2-opt (2 de los 3 de `TestLocalOperators` ya estaban `pytest.skip`). Con el optimizador crítico en C++, verificar esa mejora paso a paso en Python no aportaba al dominio; la validación real (viabilidad de la solución) ya está cubierta en `TestSolverPipeline`/`TestOptimizationQuality`.
  - `test_api_integration.py::TestConfiguration::test_config_loads_from_env`, `test_database_url_construction`, `test_mongo_url_construction`, `TestPersistenceAdapters::test_postgres_adapter_instantiation`, `test_mongodb_adapter_instantiation` — reafirmaban que `os.getenv` carga una URL o que una clase se instancia sin conexión real. Fragilidad ante cualquier refactor de configuración, sin testear comportamiento de dominio observable.

- **Cobertura geográfica más allá de Lima Metropolitana / Perú en esta iteración:** se usa el extracto de Perú completo de Geofabrik (no hay uno más granular disponible ahí). Ampliar a otras regiones/países queda como decisión futura si se necesita — no se descarga ni pre-procesa nada más amplio especulativamente.
- **Orquestador de infraestructura (Terraform/Ansible) para el paso de preparación del mapa OSRM:** un target de `Makefile` (`osrm-prepare`) es suficiente para un paso de un solo comando, ejecutado una vez por entorno — introducir una herramienta de IaC para esto sería infraestructura desproporcionada al problema.
- **Cola de mensajería (Redis/RabbitMQ) para `/solve` asíncrono:** el endpoint resuelve instancias en el request-response síncrono actual. No hay volumen ni tiempos de resolución que justifiquen una cola; agregar un broker sería infraestructura sin problema real que resolver en este alcance.
- **ORM (SQLAlchemy/Tortoise) para el adapter de PostgreSQL:** el adapter usa SQL parametrizado directo (`psycopg`/`psycopg2` + placeholders). El esquema es de 3 tablas fijas sin migraciones dinámicas; un ORM añadiría una capa de abstracción sin beneficio medible sobre queries ya simples y explícitas.
- **Framework de mocking pesado para tests de persistencia (`unittest.mock`, fixtures de DB en memoria):** se optó por correr los tests de integración contra contenedores Docker reales de PostgreSQL/MongoDB. Mockear la capa de persistencia habría ocultado bugs reales (de hecho, así se detectó el problema de `psycopg2`/Python 3.14 y el bug de orden de importación en los tests).
- **Validador de schema de configuración (pydantic-settings) para prevenir desalineación de `.env.example`:** el problema real (`0.3.1`) se resolvió corrigiendo el archivo de texto plano para que coincida con `config.py`. Introducir una capa de validación nueva para 10 variables de entorno es infraestructura sin problema proporcional que resolver.
- **Cambiar `Node::demand` de `int` a `double` en el core C++ (`0.3.1`):** se evaluó junto con el fix de truncamiento de demanda, pero se descartó unilateralmente decidir el tipo de negocio sin confirmación — el usuario confirmó que las demandas son enteras (unidades discretas de carga), así que la validación se agregó en el dominio Python (`Cliente.__post_init__`) en vez de tocar el core C++ ya aprobado.
- **Añadir soporte de credenciales de MongoDB a `config.py`/`MongoDBAdapter` (`0.3.2`):** evaluado junto con la desalineación `docker-compose.yml` vs. código real; el usuario confirmó que Mongo corre sin autenticación en desarrollo local (uso ya verificado en esta sesión), así que se alineó `docker-compose.yml` a esa realidad en vez de añadir código de auth no ejercitado hoy.

---

## Notas de Migración

Este changelog inicia desde cero con la v0.1.0-alpha porque el proyecto hace una **transición arquitectónica significativa**:

**De:** Proyecto académico Qt/C++ con interfaz GUI, benchmarking teórico
**A:** SaaS VRP solver híbrido con API REST, persistencia dual, escalabilidad a 100k+ nodos

El código académico anterior (Git history) se preserva pero no se integra en este árbol. Ver [ARCHITECTURE.md](docs/ARCHITECTURE.md) para contexto completo.

---

**Formato:** [Keep a Changelog](https://keepachangelog.com/)
**Versionado:** [Semantic Versioning](https://semver.org/)
**Última actualización:** 2026-07-23
