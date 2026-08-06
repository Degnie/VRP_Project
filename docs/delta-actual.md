<delta_aprobado>
  <resumen>
    Fix de bug real reportado en uso real: con 4 vehículos para 4 sectores
    (2 camiones + 2 furgonetas, escenario clientes_lima_100_sectorizado),
    el sistema reprogramaba ~46 de 100 pedidos. Causa raíz: split_fleet_by_sector
    reparte 1 vehículo garantizado por sector (piso mínimo de un delta
    anterior) y el resto proporcional a DEMANDA DE PESO — pero el límite
    real que provoca el exceso de 8h no es el peso (la demanda cabe
    holgadamente en 1 vehículo), es la CANTIDAD DE CLIENTES (cada uno suma
    ~15min fijos de espera vía RN-026, aparte del tiempo de conducción). Con
    25 clientes por sector y solo 1 vehículo, ese único vehículo no alcanza
    a visitarlos a todos en 8h aunque el peso sobre de capacidad — y el
    mecanismo que reasigna vehículos ociosos ante exceso de 8h
    (_reduce_vehicle_capacity_for_8h) solo mira vehículos ociosos DENTRO
    del mismo sector, que nunca existen con el piso de 1.

    Fix: split_fleet_by_sector reparte proporcional a CANTIDAD DE CLIENTES
    por sector (no peso) — un sector con más paradas recibe más vehículos
    del resto de la flota tras el piso mínimo de 1, reflejando mejor la
    carga horaria real (RN-026) en vez de la carga de peso (que ya se
    valida aparte en _trim_clients_to_fleet_capacity para exceso de
    capacidad). El piso de 1 vehículo por sector con demanda > 0 y la
    prioridad a mayor carga cuando la flota no alcanza para cubrir a todos
    los sectores se mantienen sin cambios de criterio, solo cambia la
    métrica de "carga" de peso a cantidad de clientes.

    Además: limpieza de los CSV de ejemplo de sectorización
    (clientes_lima_100/200/300_sectorizado.csv) — regenerados y validados
    contra OSRM /nearest (ninguno a más de 150m de una vía real), ya que la
    versión anterior tenía hasta 189/300 puntos en zonas sin acceso vial
    (cerros, fuera de cobertura de calles). Corregidos también 4 puntos
    menores (150-730m de vía) en clientes_lima_50.csv, de una sesión
    anterior. El bug de "rutas creadas pero no pintadas en el mapa" se
    resolvió solo (probablemente caché stale del navegador o reload
    pendiente del backend) — no requirió cambio de código, confirmado por
    el usuario tras recargar.
  </resumen>
  <clasificacion> correctiva </clasificacion>
  <ids_nuevos> ninguno </ids_nuevos>
  <ids_modificados>
    - RN-029 (Orquestación - Reparto de Flota por Sector): el reparto
      proporcional del resto de la flota (tras el piso de 1 vehículo por
      sector con demanda > 0) se calcula sobre la CANTIDAD DE CLIENTES de
      cada sector, no sobre la demanda de peso — refleja mejor la carga
      horaria real (RN-026 estima tiempo por cantidad de paradas + 15min
      fijos c/u, no por peso transportado).
  </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.10 </spec_version>
</delta_aprobado>
