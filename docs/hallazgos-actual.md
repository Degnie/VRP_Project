<hallazgos_infra>
  <contexto_operativo> El proyecto se encuentra en una fase de desarrollo local robusta con `docker-compose`, pero carece de artefactos formales para despliegue y validación continua. Se han propuesto dos requisitos básicos para madurar la infraestructura sin caer en sobreingeniería. </contexto_operativo>
  <politicas_de_seguridad> Secretos por variables de entorno (.env). Bases de datos aisladas en contenedores. </politicas_de_seguridad>
  <bugs> </bugs>
  <reglas_propuestas> 
  - [REGLA NUEVA] (RNF-004): "Empaquetado de Aplicación". El sistema debe proporcionar Dockerfiles separados para backend y frontend, usando imágenes ligeras y configuración sin privilegios de root.
  - [REGLA NUEVA] (RNF-005): "Integración Continua Básica". Se debe implementar un pipeline automatizado (ej. GitHub Actions) que corra pytest y `check_traceability.py` en cada PR hacia la rama principal.
  </reglas_propuestas>
  <descartados> </descartados>
</hallazgos_infra>
