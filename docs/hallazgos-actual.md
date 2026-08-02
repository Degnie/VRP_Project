<hallazgos_auditoria>
  <contexto> Lote activo proveniente de la curaduría de docs/PENDIENTES.md (P-01 y P-02). El objetivo es saldar la deuda de rendimiento del motor C++ y reactivar sus tests funcionales de RNF que actualmente están en cuarentena. </contexto>
  <bugs> 
  - [BUG] (P-01) Degradación inaceptable del operador 3-opt en instancias masivas. Falla los umbrales de RNF-001, RNF-002, RNF-003. (Documentado en ADR-006 y TESTING_STRATEGY.md). Requiere corregir el cuello de botella en C++.
  - [DEUDA DE SUITE] (P-02) Tests funcionales de RNF en cuarentena. Requiere quitar el marcador `spec: PENDIENTE` de `tests/performance/test_rnf_thresholds.py` y lograr que pasen en verde tras corregir P-01.
  </bugs>
  <reglas_propuestas> </reglas_propuestas>
  <descartados> </descartados>
</hallazgos_auditoria>
