<delta_aprobado>
  <resumen>
    Fix de 2 bugs reales encontrados en producción sobre la sectorización
    (RN-028/029/030, SPEC v1.6):

    1. split_fleet_by_sector reparte la flota estrictamente proporcional a
       demanda con math.floor — con flotas chicas (ej. 4 vehículos totales
       repartidos entre 4 sectores), un sector con demanda baja pero > 0
       podía recibir 0 vehículos por el redondeo hacia abajo, quedando
       completamente sin ruta (todos sus clientes postergados). Esto es lo
       que el usuario observó como "muchos puntos de Lima Este descartados"
       — no es un problema del polígono de Lima Este, es que ese sector
       recibía 0 vehículos en instancias con flota chica. Fix: todo sector
       con al menos 1 cliente recibe garantizado 1 vehículo (el más chico
       disponible que alcance) antes del reparto proporcional del resto.
       Si hay menos vehículos que sectores con demanda, los sectores de
       MENOR demanda se quedan sin flota — comportamiento esperado y
       confirmado por el usuario ("si hay menos de 4, no se entrega a un
       sector, el de menos pedidos").

    2. Instancia.__post_init__ rechaza con ValueError toda la instancia si
       la demanda total excede la capacidad total de la flota — sin
       resolver nada, ni siquiera parcialmente. En el contexto sectorizado,
       esto puede tumbar un sector entero (o el request completo, según
       dónde se propague la excepción) cuando su sub-flota asignada no
       alcanza para toda su demanda, en vez de generar una ruta con los
       clientes que sí caben y reprogramar el resto. Fix: antes de invocar
       solve_instance_with_retries en un sector, si la demanda del sector
       excede la capacidad de su sub-flota, se recortan los clientes que
       exceden esa capacidad (mismo criterio de selección — más lejanos
       primero — que ya usa _clients_to_postpone_for_8h) y se agregan
       directamente a postponed/CSV (RN-031), sin lanzar excepción.

    Sin cambios de alcance en RN-028 (asignación de sector por polígono,
    confirmado correcto — no se toca) ni en el mecanismo de reprogramación
    ya existente (RN-031-034, Fase 2).
  </resumen>
  <clasificacion> correctiva </clasificacion>
  <ids_nuevos> ninguno </ids_nuevos>
  <ids_modificados>
    - RN-029 (Orquestación - Reparto de Flota por Sector): se agrega el piso
      de 1 vehículo garantizado por sector con demanda > 0, antes del
      reparto proporcional del resto de la flota.
  </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.9 </spec_version>
</delta_aprobado>
