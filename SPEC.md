# ESPECIFICACIÓN VRP SOLVER (v1.0)

## 1. Resumen del Negocio
El sistema es un solver para el Problema de Ruteamiento de Vehículos (VRP) orientado a producción, capaz de escalar de 50 a 100k+ clientes. Optimiza rutas distribuyendo la demanda de los clientes en una flota de vehículos, minimizando el costo total (distancia) y garantizando que se respeten las restricciones de capacidad. Funciona mediante una arquitectura híbrida donde una API en Python orquesta motores de optimización de alto rendimiento escritos en C++.

## 2. Eventos de Dominio
1. **Instancia Recibida:** El orquestador recibe la definición del problema (depósito, flota, clientes).
2. **Invariantes Validadas:** Se comprueba la viabilidad matemática de la instancia antes de resolver.
3. **Optimización Iniciada:** El core C++ (o su fallback en Python) arranca la construcción de rutas semilla.
4. **Rutas Refinadas:** Se aplican operadores locales (Simulated Annealing, 3-opt) para optimizar costos.
5. **Solución Consolidada:** Se evalúan las rutas, garantizando cobertura total de clientes.
6. **Solución Persistida:** Se guarda la instancia y sus resultados asociados en base de datos.
7. **Solución Retornada:** La API devuelve la matriz de rutas óptimas y el costo total.

## 3. Glosario
* **Coordinate (Coordenada):** Punto espacial inmutable (x, y). Puede ser negativo o representar latitud/longitud.
* **Cliente:** Entidad que requiere ser visitada. Posee una ubicación y una demanda estricta, además de información de contacto opcional.
* **Depósito (Depot):** Punto central del cual parten y al cual regresan todos los vehículos.
* **Flota:** Configuración que define la cantidad de vehículos y sus capacidades de carga (homogénea o heterogénea).
* **Instancia:** Representa un problema a resolver. Agrupa 1 Depósito, 1 Flota y N Clientes.
* **Ruta:** Secuencia ordenada de clientes asignada a un vehículo específico, junto con el costo (distancia) de completarla.
* **Solución:** Estructura que engloba un conjunto de rutas válidas que resuelven una Instancia, incluyendo el costo total combinado.

## 4. Modelo de Dominio
* **Cliente:** Conoce su ubicación, identificador, demanda y datos de contacto. Controla que su demanda sea siempre válida y manejable.
* **Depósito:** Conoce su nombre y coordenadas.
* **Flota:** Conoce la cantidad de vehículos y las capacidades asignadas. Sabe calcular la capacidad total sumada del arreglo de vehículos.
* **Instancia:** Conoce su depósito, la flota, y la lista completa de clientes. Centraliza la validación de capacidad global antes de intentar resoluciones.
* **Ruta:** Conoce a qué vehículo está asignada, la secuencia de visitas (IDs de clientes) y su propio costo.
* **Solución:** Conoce a qué instancia pertenece, agrupa las distintas rutas y conoce el costo total general. Actúa como barrera de integridad para asegurar la exclusividad de visitas.

## 5. Reglas e Invariantes (RN)

* **RN-001 (Cliente - Demanda):** La demanda de un cliente debe ser mayor estricto a cero y un valor entero.
* **RN-002 (Flota - Límites):** El número de vehículos en la flota debe ser `>= 1` y la capacidad base debe ser `> 0`.
* **RN-003 (Flota - Heterogeneidad):** Si se define `capacidades_vehiculos`, debe tener una longitud idéntica a `num_vehiculos` y cada capacidad individual debe ser `> 0`.
* **RN-004 (Instancia - Unicidad):** Los identificadores (`id`) de los clientes en una instancia deben ser únicos.
* **RN-005 (Instancia - Capacidad Global):** La sumatoria de la demanda de todos los clientes no debe exceder la capacidad total de la flota.
* **RN-006 (Instancia - Límite por Vehículo):** Ningún cliente individual puede tener una demanda que exceda la capacidad del vehículo de mayor tamaño en la flota.
* **RN-007 (Ruta - Secuencia):** La secuencia de clientes visitados en una ruta no puede estar vacía.
* **RN-008 (Ruta - Costos):** El costo de una ruta no puede ser negativo (`>= 0`).
* **RN-009 (Solución - Rutas):** Toda solución debe contener al menos 1 ruta.
* **RN-010 (Solución - Costo Total):** El costo total de la solución debe ser exactamente igual a la sumatoria matemática del costo de todas las rutas individuales.
* **RN-011 (Solución - Cobertura Única):** Cada cliente que existe en la instancia debe ser visitado exactamente una vez en toda la solución.
* **RN-012 (API - Coordenadas):** Las coordenadas recibidas en los endpoints deben representar tuplas lógicas de tamaño 2 y con valores reales (longitud/latitud válidos).
* **RN-AUTH-001 (Autenticación):** Toda llamada a los endpoints protegidos requiere un token JWT válido.
* **RN-CAT-001 (Catálogo Aislado):** El catálogo de vehículos está estrictamente aislado por cuenta de cliente (Account).
* **RN-CAT-002 (Validación Catálogo):** La creación de un tipo de vehículo en el catálogo requiere pesos y volúmenes estrictamente mayores a cero.
* **RN-COV-001 (Roles):** Un usuario con rol de Repartidor tiene permisos de lectura sobre las zonas de cobertura, pero no de escritura.
* **RN-EXP-001 (Exportación):** La generación de la hoja de ruta en PDF permite el filtrado opcional por vehículo específico.
* **RN-MAT-001 (Fallback Costos):** El sistema debe caer graciosamente al cálculo de distancia euclidiana si el servicio OSRM falla o no está configurado.

## 6. Escenarios de Aceptación (CU)
* **CU-001 (Resolver Instancia):** Un usuario autenticado envía una definición de instancia (clientes, demandas, capacidad, depósito) por `POST /solve`. Si los datos superan las RNs, el sistema retorna un código `200` devolviendo un `instancia_id`, el costo total y el número de rutas creadas.
* **CU-002 (Rechazo sin Autorización):** Una petición a un endpoint protegido sin token JWT válido es rechazada inmediatamente con `401 Unauthorized`.
* **CU-003 (Listar Instancias):** Un usuario autenticado solicita historial vía `GET /instances` y el sistema retorna un arreglo JSON con los registros.
* **CU-CAT-001 (Gestión de Catálogo):** El usuario administrador puede crear, leer, actualizar y eliminar tipos de vehículos en su catálogo aislado.
* **CU-COV-001 (Gestión de Zonas):** El usuario puede definir o consultar las zonas de cobertura (polígonos geográficos) asignadas a su cuenta.
* **CU-EXP-001 (Exportar Hoja de Ruta):** El usuario genera un reporte en PDF de la solución obtenida, obteniendo un documento paginado por vehículo (o filtrado).

## 7. Casos Límite (EC)
* **EC-001 (Distancia Cero):** Un cliente se ubica en las coordenadas exactas del depósito. El costo inicial es `0.0`. El motor maneja el cálculo porcentual de optimización omitiendo divisiones por cero en este escenario.
* **EC-002 (Sobrecarga de Caracteres):** Campos de texto libre que superan los límites estrictos de la BD (VARCHAR 255/500) son interceptados devolviendo `422 Unprocessable Entity` en vez de provocar caídas de persistencia.
* **EC-003 (Falla del Core C++):** Si el módulo compilado de C++ no está accesible en el sistema anfitrión, el orquestador aplica un "fallback" transparente a implementaciones matemáticas equivalentes en Python para resolver la instancia (aunque con mayor tiempo de cómputo).

## 8. Requisitos No Funcionales (RNF)
* **RNF-001:** Resoluciones para instancias Pequeñas (< 100 nodos) en 10-50ms (CPU).
* **RNF-002:** Resoluciones para instancias Medianas (100 - 1,000 nodos) en 100-500ms (CPU).
* **RNF-003:** Resoluciones para instancias Grandes (1,000 - 10,000 nodos) en 1-5 segundos (requiere CPU moderno + 8GB RAM).

## 9. Fuera de Alcance
* **Distancias sobre alternativas a OSRM:** Valhalla queda como alternativa conceptual de ruteo, pero no está implementada ni forma parte del scope actual.
* **Simetría Euclidiana Obligatoria:** La arquitectura está diseñada para matrices de adyacencia dirigidas y asimétricas desde el C++; no se asume simetría para distancias del mundo real.
