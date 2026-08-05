<delta_aprobado>
  <resumen> 
    Se añaden múltiples características operativas a la plataforma: un Dashboard diario para el dueño, un botón de ayuda y comprobante fotográfico (Base64) para el repartidor. Adicionalmente, se introduce un cambio estructural mayor en la orquestación: se simularán ventanas de tiempo (límites de trabajo de min 5h y max 8h) no tocando el motor matemático de C++, sino implementando una orquestación inteligente de reintentos en Python que consolida rutas cortas (<5h) o posterga pedidos largos (>8h) al día siguiente. Además, se formaliza el catálogo de vehículos con suspensión (mantenimiento) y semillas por defecto (Moto, Furgoneta, Camión).
  </resumen>
  <clasificacion> estructural </clasificacion>
  <ids_nuevos> 
    - RN-023 (UI - Dashboard Diario)
    - RN-024 (UI - Botón de Ayuda)
    - RN-025 (API - Comprobante Fotográfico)
    - RN-026 (Orquestación - Límite Máximo de Ruta)
    - RN-027 (Orquestación - Optimización de Flota por Subutilización)
    - RN-CAT-003 (Estados del Vehículo)
    - RN-CAT-004 (Catálogo Base Referencial)
  </ids_nuevos>
  <ids_modificados> 
    - Sección 9 (Fuera de Alcance): Aclara que VRPTW se implementa solo a nivel orquestación en Python, no en C++.
  </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> Opción B acordada (Mantener CVRP en C++ y orquestar VRPTW con reintentos en Python). Modificar ADR-001 si aplica en la implementación. </decision_adr>
  <spec_version> v1.5 </spec_version>
</delta_aprobado>
