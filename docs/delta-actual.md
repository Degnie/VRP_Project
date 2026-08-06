<delta_aprobado>
  <resumen>
    Reemplazo de los 4 polígonos hardcodeados en sectorization.py (dados a
    mano, sin fuente verificable) por límites distritales reales de Lima
    Metropolitana, usando el GeoJSON público de joseluisq/peru-geojson-datasets
    (licencia Apache-2.0, datos atribuidos al IGN — Instituto Geográfico
    Nacional de Perú), archivo lima_callao_distritos.geojson.

    Los 43 distritos de Lima (los 7 de Callao se descartan — el sistema es
    de Lima Metropolitana, sin sector propio para Callao) se agrupan en los
    4 sectores existentes (Norte/Este/Sur/Centro) según el mapeo estándar
    de logística de Lima, aprobado por el usuario:

    - Lima Norte: Ancón, Carabayllo, Comas, Independencia, Los Olivos,
      Puente Piedra, San Martín de Porres, Santa Rosa.
    - Lima Este: Ate, Chaclacayo, Cieneguilla, El Agustino, La Molina,
      Lurigancho, San Juan de Lurigancho, Santa Anita.
    - Lima Sur: Chorrillos, Lurín, Pachacámac, Pucusana, Punta Hermosa,
      Punta Negra, San Bartolo, San Juan de Miraflores, Santa María del
      Mar, Villa El Salvador, Villa María del Triunfo.
    - Lima Centro: Barranco, Breña, Jesús María, La Victoria, Lima
      (Cercado), Lince, Magdalena del Mar, Miraflores, Pueblo Libre,
      Rímac, San Borja, San Isidro, San Luis, San Miguel, Santiago de
      Surco, Surquillo.

    assign_sector() deja de usar ray-casting manual sobre 4 polígonos
    fijos de 6-8 vértices — pasa a resolver contra los polígonos reales
    (MultiPolygon en algunos distritos con islas/exclaves) de cada uno de
    los 43 distritos, devolviendo el sector del distrito que contiene la
    coordenada. El fallback a Lima Centro para coordenadas fuera de los 43
    distritos (RN-028) se mantiene sin cambios de comportamiento.

    Datos de ejemplo (clientes_lima_100/200/300_sectorizado.csv) quedan
    sin cambios de contenido — se re-verifican contra el nuevo
    assign_sector() para confirmar que ningún punto cambia de sector
    (mismo criterio geográfico real, ahora con fronteras oficiales en vez
    de aproximaciones a mano).
  </resumen>
  <clasificacion> estructural </clasificacion>
  <ids_nuevos> ninguno </ids_nuevos>
  <ids_modificados>
    - RN-028 (Orquestación - Sectorización Geográfica): la asignación de
      sector deja de basarse en 4 polígonos aproximados dados a mano —
      pasa a usar los límites distritales reales (IGN, vía GeoJSON
      público) de los 43 distritos de Lima Metropolitana, agrupados en
      los mismos 4 sectores (Norte/Este/Sur/Centro). El fallback a Lima
      Centro para coordenadas fuera de cualquier distrito se mantiene.
  </ids_modificados>
  <ids_retirados> ninguno </ids_retirados>
  <decision_adr> ninguno </decision_adr>
  <spec_version> v1.12 </spec_version>
</delta_aprobado>
