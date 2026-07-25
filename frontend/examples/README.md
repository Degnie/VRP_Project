# Ejemplos de instancias

## clientes_lima_50.csv

Depósito en el Cercado de Lima (centro histórico) + 50 clientes distribuidos entre
18 distritos de Lima Metropolitana y Callao. Columna `peso_kg` en kilogramos por pedido
(rango 2–18 kg, valores enteros — el backend exige demanda entera), peso total = 441 kg.

Al importar este archivo, ajustá "N° vehículos" y "Capacidad por vehículo (kg)" en el
formulario para que `num_vehiculos × capacidad ≥ 441 kg` (p. ej. 5 vehículos × 100 kg).

## clientes_lima_100.csv

Mismo depósito (Cercado de Lima) + 100 clientes dentro de un radio de ~15 km del centro.
Cada punto fue validado contra OSRM (`/nearest`, descartando cualquiera a más de 150 m
de una calle) para no generar entregas en el mar, cerros sin acceso u otras zonas
inalcanzables. Peso total = 905 kg — probado end-to-end contra el backend real (10
vehículos × 100 kg) con costo real de calle de 698,888.7 m.

Requiere `OSRM_URL` configurado en `.env.local` (ver sección OSRM) — sin OSRM, 101
coordenadas siguen resolviendo por fallback euclídeo, pero el objetivo de este archivo
es probar el pipeline con distancias reales y el chunking de tabla OSRM.

## clientes_lima_multipaquete.csv

Mismo depósito, con columnas nuevas: `cliente_id` (identifica el punto de entrega),
`largo`, `ancho`, `alto` (cm, por paquete). El cliente `c3` aparece en dos filas —
mismas coordenadas, dos paquetes separados — y el importador los agrupa en un solo
punto de entrega con demanda total de 7 kg y volumen sumado. Sin columna `cliente_id`,
cada fila sigue tratándose como un cliente independiente (retrocompatible con
`clientes_lima_50.csv`/`clientes_lima_100.csv`, que no tienen esta columna).

Alias de encabezado soportados: `cliente_id`/`client_id`/`id`/`identificador`,
`largo`/`length`/`length_cm`, `ancho`/`width`/`width_cm`, `alto`/`height`/`height_cm`
(todos case-insensitive, igual que `x`/`y`/`peso_kg`).

## clientes_sjl_50.csv

Depósito en el Cercado de Lima (mismo de siempre) + 50 clientes dentro de San Juan de
Lurigancho (SJL) — un solo distrito, no repartidos por toda Lima. Cada punto fue
validado en dos pasos: OSRM `/nearest` (descarta zonas sin calle) y reverse geocoding
real vía Nominatim (confirma que el punto cae efectivamente dentro de SJL, no en un
distrito vecino) — de 97 candidatos generados, 50 se confirmaron dentro del distrito.
Peso total = 488 kg.

Útil para probar la **zona de cobertura**: el depósito (Cercado de Lima) queda fuera
de SJL a propósito — la cobertura solo filtra clientes, nunca el depósito, así que un
almacén central puede repartir en un distrito lejano sin problema. Si dibujás un
polígono de cobertura que cubra SJL, el depósito se envía igual aunque esté afuera del
polígono.

Al importar, ajustá "N° vehículos" / "Capacidad por vehículo (kg)" (o el catálogo de
vehículos) para que la capacidad total cubra los 488 kg — con los valores por defecto
del formulario (3 × 100 kg = 300 kg) el backend rechaza la instancia con 400.

## flota_vehiculos.csv

Catálogo de ejemplo con 4 tipos de vehículo típicos de una flota de reparto urbano:

| nombre | peso_kg | volumen_m3 | margen |
|---|---|---|---|
| Moto de reparto | 30 | 0.15 | 0.9 |
| Auto | 150 | 0.6 | 0.9 |
| Camioneta | 600 | 3.5 | 0.9 |
| Camión pequeño | 1500 | 9 | 0.85 |

`margen` es la fracción de la capacidad nominal que realmente se usa al resolver (0.9 =
90%, deja 10% de colchón). Se importa desde el botón "Importar catálogo (CSV/Excel)"
dentro de la sección "Catálogo de vehículos" del formulario — se guarda en
`localStorage` (`vrp:vehicle-catalog`) y queda disponible entre sesiones; después elegís
cuántas unidades de cada tipo tenés disponibles hoy en "Flota disponible hoy".

Alias de encabezado soportados: `nombre`/`name`/`vehiculo`/`tipo`,
`peso_kg`/`capacidad_peso_kg`/`weight_capacity_kg`,
`volumen_m3`/`capacidad_volumen_m3`/`volume_capacity_m3`,
`margen`/`margen_pct`/`tolerance_margin` (acepta tanto fracción `0.9` como
porcentaje `90`, todos case-insensitive).

## clientes_lima_contacto.csv

Mismo estilo de `clientes_lima_multipaquete.csv` (depósito + `cliente_id` + multi-paquete
con `c3` repetido), agregando columnas de contacto: `nombre`, `telefono`, `direccion`.
Estos datos NO se envían al backend/solver (que solo necesita coordenadas y peso) — viven
en el frontend y se muestran en la tabla de clientes y en la hoja de ruta resuelta, para
que el repartidor sepa a quién y dónde exactamente está entregando, no solo un ID y un
punto en el mapa.

La columna `direccion` puede tener comas dentro de comillas (`"Jr. X 123, Surco, casa
celeste"`) — el parser CSV soporta comillas estilo Excel/Sheets.

Alias de encabezado soportados: `nombre`/`cliente`/`customer_name`/`customer`/`name`/
`destinatario`, `telefono`/`celular`/`phone`/`phone_number`/`whatsapp`,
`direccion`/`address`/`referencia`/`address_reference` (todos case-insensitive).

La tabla de clientes muestra cada punto como una tarjeta colapsada (nombre + teléfono +
peso total) que se expande al hacer click para ver/editar X, Y, dirección y paquetes —
pensado para que 50-100+ pedidos sigan siendo manejables visualmente, sin scrollear una
lista de inputs expandidos.
