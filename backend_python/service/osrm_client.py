"""
Cliente OSRM: obtiene matrices de distancia reales (calles) vía el endpoint /table.

Uso: get_osrm_matrix(coords, base_url, max_table_size, timeout_seconds) -> matriz NxN en metros.
Lanza OSRMError si el servicio no responde o falla — el caller decide el fallback
(ver SolverOrchestrator, que cae a distancia euclídea).

IMPORTANTE: coords deben ser coordenadas geográficas reales (lon, lat).
get_osrm_matrix valida que estén en rango lon/lat válido antes de llamar a OSRM
(lanza OSRMError si no) — esto evita el caso más peligroso (coordenadas
cartesianas fuera de rango), pero no puede detectar coordenadas cartesianas
que caigan dentro de un rango lon/lat plausible por coincidencia.
"""

from typing import List, Tuple
import requests


class OSRMError(Exception):
    """OSRM no disponible, timeout, o respuesta inválida."""


def _validate_coords_are_geographic(coords: List[Tuple[float, float]]) -> None:
    """
    Verifica que las coordenadas estén en rango lon/lat válido antes de llamar
    a OSRM. Sin esto, coordenadas cartesianas/sintéticas que caigan dentro de
    un rango lon/lat plausible por coincidencia producirían una matriz "válida"
    pero sin ningún sentido, sin que OSRM pueda detectarlo por su cuenta.
    """
    for x, y in coords:
        if not (-180.0 <= x <= 180.0) or not (-90.0 <= y <= 90.0):
            raise OSRMError(
                f"coordinate ({x}, {y}) is outside valid lon/lat range — "
                "OSRM_URL requires real geographic coordinates, not cartesian/synthetic ones"
            )


def _table_request(coords: List[Tuple[float, float]], base_url: str, timeout_seconds: int) -> List[List[float]]:
    """Una sola llamada a /table para <= max_table_size coordenadas. coords en (x, y) = (lon, lat)."""
    coords_str = ";".join(f"{x},{y}" for x, y in coords)
    url = f"{base_url}/table/v1/driving/{coords_str}?annotations=distance"

    try:
        response = requests.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise OSRMError(f"OSRM request failed: {e}") from e

    if data.get("code") != "Ok":
        raise OSRMError(f"OSRM returned error code: {data.get('code')}")

    distances = data.get("distances")
    if distances is None:
        raise OSRMError("OSRM response missing 'distances' (check annotations=distance)")

    return distances


def get_osrm_matrix(
    coords: List[Tuple[float, float]],
    base_url: str,
    max_table_size: int,
    timeout_seconds: int,
) -> List[List[float]]:
    """
    Matriz de distancias NxN (metros) para las coordenadas dadas, vía OSRM /table.

    Si len(coords) > max_table_size, particiona en bloques y ensambla la matriz
    completa con múltiples llamadas (una por cada par de bloques fila/columna).

    Args:
        coords: lista de (x, y) = (lon, lat), en el mismo orden que la instancia
                (depot primero, luego clientes) para que la matriz resultante
                sea directamente indexable igual que CostMatrix.
        base_url: URL del servidor OSRM (ej. "http://localhost:5000")
        max_table_size: máximo de coordenadas por llamada /table
        timeout_seconds: timeout HTTP por llamada

    Raises:
        OSRMError: si cualquier llamada falla, el servicio no responde, o las
                   coordenadas están fuera del rango lon/lat válido.
    """
    _validate_coords_are_geographic(coords)
    n = len(coords)

    if n <= max_table_size:
        return _table_request(coords, base_url, timeout_seconds)

    # Chunking: particiona en bloques y ensambla la matriz completa pidiendo
    # submatrices fila-bloque x columna-bloque. Cada request combina un bloque
    # de fila + un bloque de columna en una sola lista de coordenadas, así que
    # el tamaño de bloque debe ser max_table_size // 2 — de lo contrario la
    # unión fila+columna podría exceder max_table_size (el límite real que
    # OSRM aplica por request), invalidando el propósito del chunking.
    block_size = max(1, max_table_size // 2)
    matrix = [[0.0] * n for _ in range(n)]
    block_ranges = [
        (start, min(start + block_size, n))
        for start in range(0, n, block_size)
    ]

    for row_start, row_end in block_ranges:
        for col_start, col_end in block_ranges:
            block_coords = coords[row_start:row_end] + coords[col_start:col_end]
            sources = list(range(0, row_end - row_start))
            destinations = list(range(row_end - row_start, len(block_coords)))

            coords_str = ";".join(f"{x},{y}" for x, y in block_coords)
            sources_str = ";".join(map(str, sources))
            destinations_str = ";".join(map(str, destinations))
            url = (
                f"{base_url}/table/v1/driving/{coords_str}"
                f"?sources={sources_str}&destinations={destinations_str}&annotations=distance"
            )

            try:
                response = requests.get(url, timeout=timeout_seconds)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                raise OSRMError(f"OSRM chunked request failed: {e}") from e

            if data.get("code") != "Ok":
                raise OSRMError(f"OSRM returned error code: {data.get('code')}")

            block_distances = data.get("distances")
            if block_distances is None:
                raise OSRMError("OSRM response missing 'distances' (check annotations=distance)")

            for i, row in enumerate(block_distances):
                for j, dist in enumerate(row):
                    matrix[row_start + i][col_start + j] = dist

    return matrix
