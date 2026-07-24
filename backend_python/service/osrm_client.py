"""
Cliente OSRM: obtiene matrices de distancia reales (calles) vía el endpoint /table.

Uso: get_osrm_matrix(coords, base_url, max_table_size, timeout_seconds) -> matriz NxN en metros.
Lanza OSRMError si el servicio no responde o falla — el caller decide el fallback
(ver SolverOrchestrator, que cae a distancia euclídea).

IMPORTANTE: coords deben ser coordenadas geográficas reales (lon, lat). Activar
OSRM_URL contra una instancia con coordenadas cartesianas/sintéticas (no geográficas)
puede producir resultados sin sentido si esos valores caen dentro de un rango
lon/lat válido por coincidencia — OSRM no tiene forma de detectar ese mal uso.
"""

from typing import List, Tuple
import requests


class OSRMError(Exception):
    """OSRM no disponible, timeout, o respuesta inválida."""


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
        OSRMError: si cualquier llamada falla o el servicio no responde.
    """
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
