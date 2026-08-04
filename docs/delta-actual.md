<delta_aprobado>
  <resumen> Abordaje del ítem P-05: eliminar la cuarentena (`spec: PENDIENTE`) de `tests/unit/test_persistence.py`. Los 9 tests ya pasan hoy contra PostgreSQL/MongoDB reales — la cuarentena era defensiva, no encubría un fallo. Ninguno citaba una regla de SPEC formal; se proponen y aprueban RN-021 (round-trip sin pérdida) y RN-022 (reconexión automática) para poder destrackear el módulo con trazabilidad real, sin inventar comportamiento nuevo. </resumen>
  <clasificacion> técnica (deuda de suite) </clasificacion>
  <ids_nuevos> RN-021 (Persistencia - Round-trip sin pérdida), RN-022 (Persistencia - Reconexión automática) </ids_nuevos>
  <ids_modificados> Ninguno </ids_modificados>
  <ids_retirados> Ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.3 </spec_version>
</delta_aprobado>
