# ADR-005: Estrategia de Verificación Condicional y Contrato de verify

**Estado:** Aceptado

## Contexto
El proyecto VRP Solver ha evolucionado hacia una arquitectura híbrida Python/C++ que depende de servicios externos para su correcta ejecución en entornos de producción: PostgreSQL, MongoDB y un servicio OSRM para enrutamiento geográfico. Adicionalmente, el núcleo algorítmico depende de que el código C++ esté compilado en el sistema anfitrión.

Para el desarrollo local y la ejecución en pipelines de Integración Continua (CI), es insostenible requerir que todos estos servicios estén levantados y configurados únicamente para comprobar la lógica de negocio y pasar la suite de pruebas.

## Decisión
Se ha decidido adoptar las siguientes estrategias para estandarizar la verificación del proyecto, sin cambiar ni agregar herramientas al stack tecnológico actual:

1. **Metodología Condicional ("Skip if not present")**
   Las pruebas de integración interactuarán con los adaptadores de base de datos y OSRM. Si las variables de entorno (`DATABASE_URL`, `MONGO_URL`, `OSRM_URL`) no están presentes en el entorno local de desarrollo (o en CI si se desea ignorarlas temporalmente), los tests relacionados a la infraestructura se saltarán automáticamente usando los marcadores integrados (`skipif`). Esto garantiza que la suite pueda devolver "verde" de forma limpia sin afectar la integridad del reporte.

2. **Contrato de `verify`**
   El comando formal de verificación de la salud del código no será un script nuevo o una herramienta ajena al ecosistema actual. El contrato de verificación se delega al `Makefile` existente. 
   La comprobación completa ("verify") consistirá en la ejecución combinada de:
   - `make test` (Llama a `pytest` para la suite principal y la API).
   - `make test-cpp` (Llama a `ctest` para probar los algoritmos aislados en C++ de manera nativa).

## Consecuencias
- **Positivas:** Reducción de la fricción en el desarrollo local al no forzar contenedores Docker innecesarios para validar refactors menores del dominio. Se respetan las herramientas actuales sin añadir complejidad extra.
- **Negativas:** Existe el riesgo teórico de que un desarrollador pase la suite local con servicios apagados sin probar la integración real. Esto debe mitigarse requiriendo que el pipeline de CI tenga todos los servicios levantados antes de fusionar código a las ramas principales.
