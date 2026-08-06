<delta_aprobado>
  <resumen>
    Fase 1 de 3 de la sectorización geográfica de Lima Metropolitana. Antes
    de resolver una instancia, los clientes se agrupan en 4 sectores fijos
    (Lima Norte, Lima Este, Lima Sur, Lima Centro) según polígonos
    geográficos predefinidos. La flota total se reparte entre los 4
    sectores en proporción a la demanda de peso de cada uno, preservando
    el mix de tipos de vehículo. RN-026/RN-027 (orquestación de reintentos
    de 5-8h) se ejecutan de forma independiente por sector, no sobre la
    instancia combinada — esto resuelve de raíz el problema de fondo
    encontrado en el escenario de 172 pedidos/15 vehículos (el solver base
    CVRP, sin noción de tiempo, llenaba un solo vehículo grande antes de
    tocar el resto de la flota; con sectores geográficamente compactos y
    subflotas más chicas, cada sector converge de forma natural sin
    necesitar el parche de reducción de capacidad).

    Las Fases 2 (prioridad de reprogramación, tope de 1 reprogramación por
    pedido) y 3 (export CSV de pedidos reprogramados) quedan fuera de este
    delta — se abordan en deltas separados una vez cerrada esta fase.
  </resumen>
  <clasificacion> estructural </clasificacion>
  <ids_nuevos>
    - RN-028 (Orquestación - Sectorización Geográfica)
    - RN-029 (Orquestación - Reparto de Flota por Sector)
    - RN-030 (Orquestación - RN-026/027 por Sector)
  </ids_nuevos>
  <ids_modificados> ninguno </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.6 </spec_version>
</delta_aprobado>
