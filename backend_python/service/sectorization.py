"""Sectorización geográfica de Lima Metropolitana (RN-028, RN-029)."""

import json
import math
from pathlib import Path
from typing import Dict, List, Optional

from backend_python.models import Coordinate, Flota

_SECTOR_FALLBACK = "Lima Centro"

# Mapeo distrito real (IGN) -> sector de negocio, aprobado por el usuario.
# Callao (7 distritos) queda deliberadamente fuera: el sistema es de Lima
# Metropolitana, sin sector propio para Callao — cae en el fallback.
_DISTRITO_A_SECTOR: Dict[str, str] = {
    "ANCON": "Lima Norte", "CARABAYLLO": "Lima Norte", "COMAS": "Lima Norte",
    "INDEPENDENCIA": "Lima Norte", "LOS OLIVOS": "Lima Norte",
    "PUENTE PIEDRA": "Lima Norte", "SAN MARTIN DE PORRES": "Lima Norte",
    "SANTA ROSA": "Lima Norte",
    "ATE": "Lima Este", "CHACLACAYO": "Lima Este", "CIENEGUILLA": "Lima Este",
    "EL AGUSTINO": "Lima Este", "LA MOLINA": "Lima Este", "LURIGANCHO": "Lima Este",
    "SAN JUAN DE LURIGANCHO": "Lima Este", "SANTA ANITA": "Lima Este",
    "CHORRILLOS": "Lima Sur", "LURIN": "Lima Sur", "PACHACAMAC": "Lima Sur",
    "PUCUSANA": "Lima Sur", "PUNTA HERMOSA": "Lima Sur", "PUNTA NEGRA": "Lima Sur",
    "SAN BARTOLO": "Lima Sur", "SAN JUAN DE MIRAFLORES": "Lima Sur",
    "SANTA MARIA DEL MAR": "Lima Sur", "VILLA EL SALVADOR": "Lima Sur",
    "VILLA MARIA DEL TRIUNFO": "Lima Sur",
    "BARRANCO": "Lima Centro", "BREÑA": "Lima Centro", "JESUS MARIA": "Lima Centro",
    "LA VICTORIA": "Lima Centro", "LIMA": "Lima Centro", "LINCE": "Lima Centro",
    "MAGDALENA DEL MAR": "Lima Centro", "MIRAFLORES": "Lima Centro",
    "PUEBLO LIBRE": "Lima Centro", "RIMAC": "Lima Centro", "SAN BORJA": "Lima Centro",
    "SAN ISIDRO": "Lima Centro", "SAN LUIS": "Lima Centro", "SAN MIGUEL": "Lima Centro",
    "SANTIAGO DE SURCO": "Lima Centro", "SURQUILLO": "Lima Centro",
}

_GEOJSON_PATH = Path(__file__).parent / "data" / "lima_callao_distritos.geojson"


def _cargar_distritos() -> List[tuple]:
    """Carga (sector, multipolygon) por cada distrito mapeado del GeoJSON.
    multipolygon: List[polygon], polygon: List[ring], ring: List[(x, y)] —
    primer ring es el contorno exterior, el resto son huecos/islas."""
    with open(_GEOJSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    distritos = []
    for feature in data["features"]:
        nombre = feature["properties"]["distrito"]
        sector = _DISTRITO_A_SECTOR.get(nombre)
        if sector is None:
            continue  # Callao u otro distrito no mapeado
        distritos.append((sector, feature["geometry"]["coordinates"]))
    return distritos


# Polígonos por sector "a mano" (SECTORES) reemplazados por los 43
# distritos reales del IGN — se guarda una sola vez al importar el módulo,
# el costo de evaluar ~72k vértices por punto es trivial para instancias
# de cientos de clientes.
_DISTRITOS = _cargar_distritos()

# Nombres de sectores disponibles (para callers que iteraban SECTORES.keys()).
SECTORES: List[str] = ["Lima Norte", "Lima Este", "Lima Sur", "Lima Centro"]
SECTOR_POR_DISTRITO: Dict[str, str] = dict(_DISTRITO_A_SECTOR)


def _point_in_ring(x: float, y: float, ring: List[List[float]]) -> bool:
    """Ray casting estándar: True si (x, y) cae dentro de `ring`."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _point_in_multipolygon(x: float, y: float, multipolygon: List) -> bool:
    """True si (x, y) cae dentro de alguno de los polígonos del distrito
    (islas/exclaves incluidos), respetando huecos (rings != el primero)."""
    for polygon in multipolygon:
        if _point_in_ring(x, y, polygon[0]) and not any(
            _point_in_ring(x, y, hueco) for hueco in polygon[1:]
        ):
            return True
    return False


def assign_sector(coord: Coordinate) -> str:
    """Sector geográfico al que pertenece `coord` (RN-028), resuelto contra
    los límites distritales reales de Lima Metropolitana (IGN). Si no cae
    en ninguno de los 43 distritos mapeados (incluye estar en Callao, sin
    sector propio, o fuera de Lima), cae en Lima Centro (fallback) — sin
    esto, un pedido en el borde de la ciudad quedaría sin sector asignado."""
    for sector, multipolygon in _DISTRITOS:
        if _point_in_multipolygon(coord.x, coord.y, multipolygon):
            return sector
    return _SECTOR_FALLBACK


def split_fleet_by_sector(
    flota: Flota, num_clientes_por_sector: Dict[str, int]
) -> Dict[str, Optional[Flota]]:
    """Reparte `flota` entre los sectores de `num_clientes_por_sector` en
    proporción a la CANTIDAD DE CLIENTES de cada uno (RN-029), preservando
    el mix de tipos de vehículo — cada TIPO de vehículo (agrupado por
    capacidad idéntica: ej. las 8 motos de 30kg, los 7 camiones de 1500kg)
    se reparte proporcionalmente entre sectores por separado, en vez de
    repartir la lista completa en bloques contiguos ordenados por
    capacidad.

    Bug real: repartir por PESO de demanda (versión anterior de esta
    función) le daba más vehículos a un sector con pocos clientes de mucho
    peso individual que a uno con muchos clientes de poco peso c/u — pero
    RN-026 estima el tiempo de una ruta por CANTIDAD de paradas (~15min
    fijos c/u) más conducción, no por peso transportado. Un sector con
    muchos clientes dispersos podía quedar con 1 solo vehículo (insuficiente
    para cubrir tantas paradas en 8h) mientras otro con pocos clientes mal
    proporcionalmente se llevaba más flota de la que necesitaba — 100
    pedidos parejos entre 4 sectores y 4 vehículos reprogramaba ~46% por
    esto. La validación de exceso de PESO por sector sigue existiendo
    (ver _trim_clients_to_fleet_capacity en solver_orchestrator.py), solo
    cambia qué métrica decide CUÁNTOS vehículos recibe cada sector.

    Bug real de una versión anterior (previo a este cambio de métrica):
    repartir la lista entera ordenada de mayor a menor en bloques
    contiguos podía dejar TODOS los camiones grandes en el primer sector
    procesado y todas las motos chicas en el siguiente, sin importar si
    ese sector realmente tenía la carga que necesitaba esa capacidad — un
    sector con 89% de la carga pero que recibía solo motos por el
    redondeo terminaba con capacidad total menor a su propia demanda de
    peso, rechazado por Instancia.__post_init__ (RN-005) antes de poder
    resolverse. Repartir cada tipo por separado evita que un sector se
    quede sin la capacidad grande que necesita solo por el orden de
    asignación.

    Un sector sin vehículos asignados es None — Flota exige
    num_vehiculos >= 1, no puede representar "0 vehículos" con una
    instancia propia.
    """
    capacidades_todas = flota.capacidades_vehiculos or (
        [flota.capacidad_por_vehiculo] * flota.num_vehiculos
    )
    total_clientes = sum(num_clientes_por_sector.values())

    if total_clientes <= 0:
        return {nombre: None for nombre in num_clientes_por_sector}

    capacidades_disponibles = sorted(capacidades_todas)  # ascendente: se dona la más chica primero
    capacidades_por_sector: Dict[str, List[float]] = {nombre: [] for nombre in num_clientes_por_sector}

    # Piso de 1 vehículo por sector con clientes > 0 (RN-029), reservado
    # ANTES del reparto proporcional del resto. Bug real: repartir
    # estrictamente proporcional (math.floor) podía dejar un sector con
    # pocos clientes pero > 0 en 0 vehículos — quedaba completamente sin
    # ruta, sus clientes se descartaban/postergaban en bloque (reportado
    # como "Lima Este descartado"). Si la flota total no alcanza para
    # cubrir el piso de todos los sectores con clientes, se prioriza a los
    # de MÁS clientes primero — el/los de menos clientes se quedan sin
    # flota, comportamiento esperado y confirmado por el negocio.
    sectores_con_clientes_desc = [
        nombre for nombre, _ in sorted(num_clientes_por_sector.items(), key=lambda kv: kv[1], reverse=True)
        if num_clientes_por_sector[nombre] > 0
    ]
    for nombre in sectores_con_clientes_desc:
        if not capacidades_disponibles:
            break
        capacidades_por_sector[nombre].append(capacidades_disponibles.pop(0))

    # Agrupar el resto por tipo (capacidad idéntica) para repartir cada
    # grupo proporcionalmente, preservando el mix real de la flota.
    tipos: Dict[float, int] = {}
    for cap in capacidades_disponibles:
        tipos[cap] = tipos.get(cap, 0) + 1

    nombres_ordenados = sorted(num_clientes_por_sector.items(), key=lambda kv: kv[1], reverse=True)

    for capacidad, cantidad in tipos.items():
        conteos: Dict[str, int] = {}
        for nombre, num_clientes in num_clientes_por_sector.items():
            proporcion = num_clientes / total_clientes
            conteos[nombre] = math.floor(proporcion * cantidad)

        # Redondeo hacia abajo puede dejar unidades de este tipo sin
        # repartir — se asignan al sector con más clientes, una por una.
        sobrantes = cantidad - sum(conteos.values())
        idx = 0
        while sobrantes > 0 and nombres_ordenados:
            nombre, num_clientes = nombres_ordenados[idx % len(nombres_ordenados)]
            if num_clientes > 0:
                conteos[nombre] += 1
                sobrantes -= 1
            idx += 1
            if idx > len(nombres_ordenados) * cantidad + 1:
                break  # ningún sector restante tiene clientes > 0

        for nombre, n in conteos.items():
            capacidades_por_sector[nombre].extend([capacidad] * n)

    resultado: Dict[str, Optional[Flota]] = {}
    for nombre, capacidades_sector in capacidades_por_sector.items():
        if not capacidades_sector:
            resultado[nombre] = None
            continue
        capacidades_sector = sorted(capacidades_sector, reverse=True)
        resultado[nombre] = Flota(
            num_vehiculos=len(capacidades_sector),
            capacidad_por_vehiculo=capacidades_sector[0],
            capacidades_vehiculos=capacidades_sector,
        )
    return resultado
