<delta_aprobado>
  <resumen>
    Fix de 3 bugs reales reportados en uso real:

    1. (Punto 2 del reporte) Instancia.__post_init__ rechaza con ValueError
       toda la instancia si la demanda total excede la capacidad total de
       la flota — esto corre en /solve ANTES de sectorizar, así que el
       endpoint devolvía 400 sin dar oportunidad a solve_instance_sectorized
       de recortar por sector y postergar solo los clientes que no caben
       (RN-029, ya implementado en un delta anterior, pero nunca se
       ejecutaba porque la Instancia global explotaba antes). Fix: nuevo
       parámetro opcional `validar_capacidad_total: bool = True` en
       Instancia — el endpoint /solve (que siempre sectoriza después) lo
       pasa en False; el resto de los callers (reschedule, tests directos
       de Instancia, etc.) mantienen la validación estricta sin cambios.

    2. (Puntos 1 y 3 del reporte) "Todos los pedidos reprogramados" en
       rutas recién creadas: causa raíz confirmada con el usuario — al
       reusar el mismo instancia_id (típicamente el valor por defecto del
       formulario) entre pruebas con CSVs distintos, save_instance()
       preserva delivery_status de clientes con el mismo id numérico entre
       resoluciones (diseñado para no perder progreso de entrega al
       corregir/re-resolver LA MISMA instancia). Si el set de clientes
       nuevo es sustancialmente distinto al anterior (otro CSV cargado bajo
       el mismo id), esa preservación contamina pedidos nuevos con
       delivery_status='reprogramado'/'entregado' de una corrida anterior
       no relacionada. Fix: antes de persistir, si menos del 50% de los ids
       del payload nuevo coinciden en coordenadas (x,y) con los que ya
       había en DB para ese instancia_id, se resetea delivery_status a
       'pendiente' para TODOS los clientes de esa instancia antes del
       upsert — se asume una instancia distinta reusando el mismo nombre
       por accidente, no una corrección incremental de la misma.

    3. (Punto 4 del reporte) GeoJSON real de distritos de Lima — CONFIRMADO
       fuera de este delta, se aborda en un delta separado después de
       cerrar estos 3 fixes.
  </resumen>
  <clasificacion> correctiva </clasificacion>
  <ids_nuevos>
    - RN-036 (Persistencia - Reset de Estados en Reuso de instancia_id): si
      al guardar una instancia menos del 50% de los ids de clientes del
      payload nuevo coinciden en coordenadas con los que ya existían en DB
      para ese mismo instancia_id, se resetea delivery_status a
      'pendiente' para todos los clientes de esa instancia antes de
      persistir — evita que un instancia_id reusado con contenido no
      relacionado herede estados de entrega/reprogramación de una corrida
      anterior sin conexión real.
  </ids_nuevos>
  <ids_modificados>
    - RN-005 (Invariantes - Capacidad total, implícita en el modelo
      Instancia): se agrega la excepción explícita de que /solve puede
      saltarse esta validación a nivel de la instancia global cuando va a
      sectorizar, dejando que RN-029 decida el recorte por sector.
  </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.11 </spec_version>
</delta_aprobado>
