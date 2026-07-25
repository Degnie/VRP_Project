# Auditoría como cliente (dueño de empresa de última milla)

Evaluación del producto puesta en el rol de dueño de una empresa que recibe paquetes de
Temu/Alibaba/Shein y reparte por Lima Metropolitana, con los 5 sombreros: dueño,
jefe de operaciones, repartidor, comprador final del contenedor (importador), y
cliente final que espera el paquete.

Estado a la fecha de esta auditoría (2026-07-24).

## Cuadro de hallazgos

| # | Hallazgo | Rol que lo detectó | Estado | Detalle |
|---|---|---|---|---|
| 1 | No hay nombre/teléfono/dirección de texto por cliente — solo coordenadas | Dueño, repartidor, importador | ✅ **Implementado** | `ClientGroup.customerName/customerPhone/address`, captura por CSV/UI, mostrado en hoja de ruta resuelta. Ver `clientes_lima_contacto.csv`. |
| 2 | Tabla de clientes inmanejable con 50-100+ pedidos (card expandida por fila) | Dueño, jefe de operaciones | ✅ **Implementado** | Tarjetas colapsables: nombre/teléfono/peso visible por defecto, expandir solo para editar detalle. |
| 3 | Parser CSV no soporta comas dentro de comillas (direcciones reales las rompían) | — (encontrado al implementar #1) | ✅ **Implementado** | `src/lib/csv.ts` reescrito con parser CSV con comillas estilo Excel/Sheets. |
| 4 | Catálogo de vehículos y zona de cobertura viven solo en `localStorage` del navegador — no se comparten entre PCs/usuarios | Dueño, jefe de operaciones | ⬜ **Pendiente** | Requiere persistir en el backend (Postgres) + algún tipo de identidad de "negocio/cuenta", no solo de instancia. |
| 5 | Sin login ni roles de usuario — cualquiera con la URL ve y edita todo | Dueño | ⬜ **Pendiente** | Autenticación + autorización no existen en absoluto hoy. |
| 6 | No hay forma de exportar/imprimir la hoja de ruta para dársela al repartidor | Jefe de operaciones, repartidor | ⬜ **Pendiente** | Falta botón de exportar a PDF/CSV imprimible de la solución resuelta. |
| 7 | Sin estado de entrega post-reparto (entregado / no encontrado / rechazado) | Jefe de operaciones, repartidor | ⬜ **Pendiente** | El sistema calcula rutas una vez; no hay ciclo de vida del pedido después de salir el vehículo. |
| 8 | Sin versión/vista mobile — todo pensado para escritorio ancho | Repartidor | ⬜ **Pendiente** | Sidebar fijo de 360px + mapa; no hay layout responsive para el caso de uso real (repartidor con celular). |
| 9 | Sin relación con número de guía/tracking del agregador (Shopee/Temu/etc.) | Importador | ⬜ **Pendiente** | Solo existe `cliente_id` genérico; no hay campo dedicado a folio de compra o tracking externo. |
| 10 | Sin reprogramación de pedidos no entregados al día siguiente | Importador, jefe de operaciones | ⬜ **Pendiente** | Cada resolución es una foto de un instante; no hay noción de "pedidos pendientes que arrastro". |
| 11 | ETA estimado por parada, mostrado al repartidor/cliente final | Repartidor, cliente final | ✅ **Ya existía** (Fase 1 anterior) | Rango horario aproximado post-solve, con aviso explícito de que es estimado, no exacto. |
| 12 | Encabezado "Contacto" se corta visualmente en el sidebar angosto (360px) | Dueño (detalle visual) | ⬜ **Pendiente** (menor) | Ajuste de CSS, no bloqueante — anotado durante la verificación visual del punto 1-2. |

## Resumen por estado

- **Implementado en esta ronda:** #1, #2, #3
- **Ya existía de una fase anterior:** #11
- **Pendiente:** #4, #5, #6, #7, #8, #9, #10, #12

## Notas

- Los puntos #4 y #5 (persistencia multi-usuario, autenticación) son la base para casi
  todo lo demás que falta — sin eso, cada mejora queda atada a "el navegador de una sola
  persona en una sola PC".
- El punto #6 (exportar/imprimir) es probablemente el de mayor impacto inmediato con
  menor esfuerzo: sin poder sacar la ruta del navegador, el valor del cálculo no llega
  al repartidor en la calle.
- Los puntos #7, #9, #10 apuntan todos a lo mismo: el producto hoy es una **calculadora
  de rutas de un solo uso**, no un sistema operativo de reparto diario con ciclo de vida
  de pedido. Es una decisión de alcance mayor (probablemente una fase separada), no un
  ajuste chico.
