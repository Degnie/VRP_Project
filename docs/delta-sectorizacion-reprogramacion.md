# Delta: Sectorización + Reprogramación (SPEC v1.6 → v1.8)

Documento de auditoría del delta completo (3 fases) cerrado en esta sesión.
Rango de commits: `672dc8e..d5ce2c1` (16 commits, todos autor `Denis`, sin
co-autoría de asistente).

## 1. Origen: el bug que disparó el delta

**Reporte real:** 172 pedidos, 8 motos + 7 camiones → el sistema generaba
**1 sola ruta**, reprogramando 147 clientes al día siguiente.

**Causa raíz:** el core del solver (`SolverOrchestrator`) es un CVRP puro —
optimiza distancia + capacidad de peso, sin ninguna noción de tiempo/duración
de ruta. La orquestación VRPTW (límite de 8h, RN-026/027) vive enteramente
en Python, por fuera del solver. Con una flota grande y heterogénea, un solo
camión de 1500kg tenía capacidad de sobra para absorber los 172 pedidos —el
algoritmo greedy lo llenó por completo (ruta de ~66h) sin tocar los otros 14
vehículos disponibles, porque nada en el CVRP base mira cuántos vehículos
quedan ociosos.

**Fix inmediato (antes de este delta, commits `672dc8e`, `6373e4c`):**
correcciones puntuales de RN-026/RN-027 (reducción de flota/capacidad en
lote en vez de de a 1 vehículo por iteración). Funcionaron, pero el usuario
propuso una solución estructural: dividir Lima en sectores geográficos fijos
y resolver cada uno de forma independiente con su propia sub-flota — sectores
compactos convergen bajo 8h de forma natural, sin necesitar heurísticas de
reducción de capacidad agresivas.

## 2. Fase 1 — Sectorización geográfica (SPEC v1.6)

Commits: `0c23e5d` (test rojo) → `715762c` (implementación) → `78678bf` (changelog)

| Regla | Qué hace |
|---|---|
| RN-028 | Cada cliente se asigna a 1 de 4 sectores fijos de Lima Metropolitana (Norte/Este/Sur/Centro) según el polígono geográfico que contiene su coordenada. Fallback a Lima Centro si no cae en ninguno. |
| RN-029 | La flota total se reparte entre los 4 sectores en proporción a la demanda de peso de cada uno, preservando el mix de tipos de vehículo (no bloques contiguos de capacidades). |
| RN-030 | RN-026/RN-027 (orquestación de 5h-8h) corren de forma independiente por sector, cada uno con su propia sub-flota y sub-lista de clientes. |

**Archivos nuevos:** `backend_python/service/sectorization.py`
(`assign_sector`, `split_fleet_by_sector`, point-in-polygon ray-casting
manual, sin dependencia nueva).

**Función nueva:** `solve_instance_sectorized()` en `solver_orchestrator.py`
— agrupa clientes por sector, reparte flota, corre
`solve_instance_with_retries()` por sector, combina rutas con `vehicle_id`
renumerado (sin colisiones entre sectores).

**Bugs reales encontrados y corregidos durante la implementación:**
- Reparto de flota por bloques contiguos de capacidad podía dejar un sector
  de alta demanda solo con vehículos chicos (insuficientes) — corregido a
  reparto proporcional por tipo de vehículo.
- Doble conteo RN-011: si el retry loop postergaba clientes en su última
  vuelta permitida sin volver a resolver, esos clientes quedaban contados
  tanto en una ruta como en `postponed` — corregido saneando `solution` en
  el momento exacto en que se decide postergar.

## 3. Fase 2 — Prioridad de reprogramación vía CSV (SPEC v1.7)

Commits: `55833ea` (test rojo) → `fa852ea` (implementación) → `cc7bfe0` (changelog)

Decisión de diseño explícita del usuario: **no** reprogramación automática
en base de datos. Todo pedido no entregado (por cualquier motivo) se
registra en un CSV en disco por cuenta, y el operario decide manualmente
cuándo incorporarlo al día siguiente.

| Regla | Qué hace |
|---|---|
| RN-031 | Todo cliente no entregado (postpone de RN-026, o cierre de jornada vía `POST /instances/{id}/reschedule` con estado pendiente/no_encontrado/rechazado) se agrega/actualiza en `reprogramados_{account_id}.csv`, con snapshot completo del pedido. |
| RN-032 | Tope de prioridad = 1. Un cliente que ya tiene prioridad 1 y vuelve a fallar no sube más — se marca `force_include=true`. |
| RN-033 | Un cliente `force_include=true` nunca se postpone por RN-026, aunque su ruta final supere las 8h. |
| RN-034 | Una fila del CSV se borra únicamente cuando el `solve` que la incluyó termina OK **y** el cliente quedó en una ruta real (no postergado de nuevo). Nunca se borra en el momento de "agregar" — evita perder el registro si el proceso se cae entre el merge y el solve. |

**Archivo nuevo:** `backend_python/service/reprogramados_csv.py`
(`read_pending`, `upsert`, `remove`).

**Endpoints nuevos:**
- `GET /reprogramados/pending` — conteo + detalle de pendientes de la cuenta.
- `POST /reprogramados/merge` — snapshot completo de los ids pedidos, para
  que el frontend los agregue a la instancia en construcción.

**Corrección de diseño real durante la implementación:** la primera versión
del CSV guardaba solo `cliente_id`. Se detectó al implementar el merge que
`cliente.id` **no es único global** — se reusa (1, 2, 3...) en cada
instancia nueva, y la instancia original puede haber sido borrada para
cuando el operario decide mezclar el pendiente. Se corrigió a snapshot
completo (coordenadas, demanda, contacto) por fila antes de seguir.

## 4. Fase 3 — Descarga del CSV (SPEC v1.8)

Commits: `8595d73` (test rojo) → `834bd83` (implementación) → `d5ce2c1` (changelog)

| Regla | Qué hace |
|---|---|
| RN-035 | `GET /reprogramados/export.csv` descarga el archivo real de la cuenta (`text/csv`, `Content-Disposition: attachment`), mismo patrón que `GET /solutions/{id}/export.pdf`. `404` si no hay pendientes (no un CSV vacío con 200). |

Import (subir un CSV editado a mano) se descartó explícitamente — la edición
de un pedido reprogramado ya pasa por `PATCH /clients/{id}` antes de
reprogramar, no por editar el archivo directamente.

## 5. Verificación (estado final, commit `d5ce2c1`)

```
287 passed, 3 skipped, 10379 warnings in 126.07s (0:02:06)
```
```
IDs en SPEC.md: 63
IDs anotados en tests/: 63
Todas las reglas de SPEC.md tienen al menos un test anotado.
```

- Suite completa (`python -m pytest tests/`) verde de punta a punta.
- `scripts/check_traceability.py`: 63/63 reglas de `SPEC.md` con al menos
  un test anotado (`spec: RN-XXX` en docstring).
- 10 tests nuevos agregados en este delta: `test_sectorization.py` (ya
  existía de Fase 1), `test_reprogramados_csv.py` (7 tests unitarios),
  `test_force_include_ids_skips_postponement`, 3 tests de integración en
  `test_solver_end_to_end.py`, 6 tests de integración en
  `test_order_lifecycle.py` (reschedule→CSV, merge, export×3).

## 6. Qué NO se hizo (fuera de alcance, explícito)

- Reprogramación automática en DB (Fase 2 la descartó a propósito).
- Import de CSV editado a mano (Fase 3 lo descartó a propósito).
- UI/frontend: este delta es 100% backend — no hay componente React para
  "agregar reprogramados automáticamente" ni botón de descarga del CSV
  todavía. Los 3 endpoints (`GET /pending`, `POST /merge`,
  `GET /export.csv`) están listos para que el frontend los consuma.
- El test `test_sectorized_covers_every_client_no_duplicates` (Fase 1,
  escenario real de 172 clientes vía OSRM) verifica solo invariantes
  estructurales (cobertura completa, sin duplicados) y no un límite
  absoluto de horas — el corredor real vía OSRM tiene variabilidad
  run-to-run genuina (`OSRM_MAX_TABLE_SIZE` fragmenta la matriz de costos
  en llamadas HTTP reales), documentado en el docstring del test.

## 7. Cómo reproducir la verificación

```bash
set -a && source .env.local && set +a
python -m pytest tests/ -q
python scripts/check_traceability.py
```

Requiere Postgres (`vrp-postgres`, puerto 5433), MongoDB (`vrp_mongo`,
puerto 27017) y OSRM (`vrp_project-osrm-1`, puerto 5000) corriendo — sin
Postgres/Mongo, `tests/integration/test_order_lifecycle.py` se salta
completo (`skipif`).
