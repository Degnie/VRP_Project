"""Sectorización geográfica de Lima Metropolitana (RN-028, RN-029)."""

import math
from typing import Dict, List, Optional

from backend_python.models import Coordinate, Flota

# Polígonos por sector, dados por el negocio (coordenadas [x=lon, y=lat]).
# Lima Centro es el sector de fallback: un cliente fuera de los 4 polígonos
# cae ahí (RN-028) en vez de quedar sin sector.
SECTORES: Dict[str, List[Coordinate]] = {
    "Lima Norte": [
        Coordinate(-77.22, -11.70), Coordinate(-76.95, -11.70), Coordinate(-76.83, -11.78),
        Coordinate(-76.80, -11.90), Coordinate(-76.82, -12.00), Coordinate(-77.00, -12.05),
        Coordinate(-77.22, -12.00),
    ],
    "Lima Este": [
        Coordinate(-76.82, -11.78), Coordinate(-76.70, -11.85), Coordinate(-76.68, -12.05),
        Coordinate(-76.69, -12.25), Coordinate(-76.72, -12.40), Coordinate(-76.84, -12.38),
        Coordinate(-76.90, -12.18), Coordinate(-76.88, -11.95),
    ],
    "Lima Sur": [
        Coordinate(-77.22, -12.18), Coordinate(-77.05, -12.18), Coordinate(-76.90, -12.20),
        Coordinate(-76.84, -12.38), Coordinate(-76.90, -12.50), Coordinate(-77.05, -12.55),
        Coordinate(-77.22, -12.50),
    ],
    "Lima Centro": [
        Coordinate(-77.10, -12.00), Coordinate(-76.88, -12.00), Coordinate(-76.86, -12.08),
        Coordinate(-76.90, -12.18), Coordinate(-77.05, -12.18), Coordinate(-77.12, -12.10),
    ],
}

_SECTOR_FALLBACK = "Lima Centro"


def _point_in_polygon(point: Coordinate, polygon: List[Coordinate]) -> bool:
    """Ray casting estándar: True si `point` cae dentro de `polygon`."""
    x, y = point.x, point.y
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i].x, polygon[i].y
        xj, yj = polygon[j].x, polygon[j].y
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def assign_sector(coord: Coordinate) -> str:
    """Sector geográfico al que pertenece `coord` (RN-028). Si no cae en
    ninguno de los 4 polígonos, cae en Lima Centro (fallback) — sin esto,
    un pedido en el borde de la ciudad quedaría sin sector asignado."""
    for nombre, polygon in SECTORES.items():
        if nombre == _SECTOR_FALLBACK:
            continue
        if _point_in_polygon(coord, polygon):
            return nombre
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
