<delta_aprobado>
  <resumen>
    Fase 2 de 3: prioridad de reprogramación vía CSV por cuenta, sin
    reprogramación automática en DB. Todo pedido que no se entrega en el día
    (por cualquier motivo: RN-026 postpone por exceso de 8h, o cierre de
    jornada con estado no-terminal pendiente/no_encontrado/rechazado vía
    POST /instances/{id}/reschedule) se agrega/actualiza en un CSV en disco
    por account_id, con su reprogramming_priority incrementada (tope 1 — no
    sube más allá de 1, se marca force_include=true en su lugar).

    El operario, al entrar a la pantalla de nueva instancia, puede consultar
    cuántos reprogramados hay pendientes (GET /reprogramados/pending) y
    agregarlos automáticamente a la instancia que está armando. Los pedidos
    con force_include=true deben incluirse sí o sí en el solve aunque el
    resultado supere las 8h de RN-026 (no se les vuelve a aplicar el postpone).

    Las filas del CSV NO se borran en el momento de "agregar automáticamente"
    (evita perder el registro si el proceso se interrumpe entre el merge y el
    solve) — se borran recién cuando el solve de esa instancia termina OK y
    el cliente efectivamente quedó en una ruta de la solución (no en
    postponed). Si en ese mismo solve el cliente vuelve a quedar postponed,
    RN-026 lo re-escribe en el CSV en la misma llamada, ya con
    force_include=true si correspondía.

    Fase 3 (si aún aplica tras esta fase) queda fuera de este delta.
  </resumen>
  <clasificacion> estructural </clasificacion>
  <ids_nuevos>
    - RN-031 (Reprogramación - CSV de Pendientes por Cuenta): todo cliente
      que no se entrega en el día (RN-026 postpone, o cierre de jornada vía
      reschedule con estado pendiente/no_encontrado/rechazado) se
      agrega/actualiza en un archivo CSV en disco por account_id
      (reprogramados_{account_id}.csv), incrementando su
      reprogramming_priority.
    - RN-032 (Reprogramación - Tope de Prioridad): reprogramming_priority
      tiene tope 1. Un cliente que ya tiene priority=1 y vuelve a no
      entregarse no incrementa más — se marca force_include=true en su fila
      del CSV.
    - RN-033 (Reprogramación - Inclusión Forzada): al resolver una instancia
      que incluye clientes con force_include=true, RN-026 (postpone por
      exceso de 8h) no se les aplica — quedan en la ruta aunque el resultado
      supere las 8h.
    - RN-034 (Reprogramación - Consumo del CSV): una fila del CSV se elimina
      únicamente cuando el solve de la instancia que la incluyó termina
      exitosamente Y el cliente quedó en una ruta de la solución (no en
      postponed). Si vuelve a quedar postponed en el mismo solve, se
      re-escribe en el CSV en la misma llamada.
  </ids_nuevos>
  <ids_modificados> ninguno </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.7 </spec_version>
</delta_aprobado>
