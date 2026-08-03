<hallazgos_infra>
  <contexto_operativo> Auditoría de infraestructura superada. El proyecto cuenta ahora con contenedores limpios (imágenes slim/alpine, non-root user) para backend y frontend, y con un pipeline de Integración Continua (GitHub Actions) configurado para frenar regresiones, respetando íntegramente las métricas de los RNF recién implementados. </contexto_operativo>
  <politicas_de_seguridad> Secretos por variables de entorno (.env). Ejecución de contenedores de app como usuarios sin privilegios (appuser/nginx). </politicas_de_seguridad>
  <bugs> </bugs>
  <reglas_propuestas> </reglas_propuestas>
  <descartados> </descartados>
</hallazgos_infra>
