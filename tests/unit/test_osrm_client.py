"""
Tests para el cliente OSRM: matriz simple, chunking, y propagación de errores.
Se activan solo si OSRM_URL está configurado y el servicio responde (mismo
patrón skipif que test_persistence.py para Postgres/Mongo).

Técnico (infraestructura del cliente HTTP hacia OSRM), sin mapear a una
regla de dominio — el fallback OSRM→euclídea (RN-MAT-001) ya está cubierto
aparte en test_optimizers.py::TestCostMatrixFallback. Cuarentena permanente,
ver TESTING_STRATEGY.md §4.
"""

import os
from unittest.mock import patch, MagicMock

import pytest
from backend_python.service.osrm_client import get_osrm_matrix, OSRMError

OSRM_AVAILABLE = bool(os.getenv("OSRM_URL"))


def test_osrm_matrix_raises_on_unreachable_host():
    """Sin servicio OSRM disponible, get_osrm_matrix debe lanzar OSRMError (no colgarse)."""
    coords = [(-77.03, -12.05), (-77.02, -12.04)]
    with pytest.raises(OSRMError):
        get_osrm_matrix(
            coords,
            base_url="http://localhost:59999",
            max_table_size=100,
            timeout_seconds=1,
        )


def test_osrm_matrix_rejects_non_geographic_coordinates():
    """Coordenadas cartesianas/sintéticas fuera de rango lon/lat deben rechazarse
    ANTES de intentar cualquier llamada HTTP (no requiere OSRM real ni red)."""
    coords = [(0.0, 0.0), (10.0, 10.0), (500.0, 500.0)]  # 500 fuera de rango lon/lat
    with pytest.raises(OSRMError, match="outside valid lon/lat range"):
        get_osrm_matrix(
            coords,
            base_url="http://localhost:59999",  # nunca se llega a usar
            max_table_size=100,
            timeout_seconds=1,
        )


def test_osrm_matrix_rejects_null_distance_cell():
    """Bug real: OSRM devuelve null en una celda de distances cuando no hay
    ruta vial entre dos coordenadas (islas, tramos desconectados, cobertura
    incompleta del extracto) — sin este chequeo, None llega hasta
    np.asarray(dtype=float64) y se convierte en NaN silencioso, que RN-008
    (costo >= 0) nunca detecta porque NaN < 0 es False en IEEE 754. El caller
    (SolverOrchestrator) espera OSRMError para activar el fallback euclidiano
    (RN-MAT-001) — sin esto, /solve respondía 200 con total_cost: NaN.

    spec: RN-MAT-001
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": "Ok",
        "distances": [[0.0, None], [None, 0.0]],
        "sources": [{"distance": 0.0}, {"distance": 0.0}],
        "destinations": [{"distance": 0.0}, {"distance": 0.0}],
    }
    mock_response.raise_for_status.return_value = None

    with patch("requests.get", return_value=mock_response):
        with pytest.raises(OSRMError, match="null distance"):
            get_osrm_matrix(
                [(-77.03, -12.05), (-77.02, -12.04)],
                base_url="http://localhost:59999",
                max_table_size=100,
                timeout_seconds=1,
            )


@pytest.mark.skipif(not OSRM_AVAILABLE, reason="OSRM not configured")
class TestOSRMIntegration:
    """Tests contra un servicio OSRM real."""

    def test_small_matrix(self):
        """Matriz NxN correcta para pocas coordenadas (una sola llamada /table)."""
        coords = [(-77.03, -12.05), (-77.02, -12.04), (-77.01, -12.03)]
        matrix = get_osrm_matrix(
            coords,
            base_url=os.getenv("OSRM_URL"),
            max_table_size=100,
            timeout_seconds=5,
        )
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)
        assert matrix[0][0] == 0.0

    def test_chunked_matrix_matches_single_call(self):
        """Con max_table_size pequeño (fuerza chunking), la matriz debe ser
        equivalente a pedirla en una sola llamada."""
        coords = [(-77.03, -12.05), (-77.02, -12.04), (-77.01, -12.03), (-77.00, -12.02)]

        single = get_osrm_matrix(coords, base_url=os.getenv("OSRM_URL"), max_table_size=100, timeout_seconds=5)
        chunked = get_osrm_matrix(coords, base_url=os.getenv("OSRM_URL"), max_table_size=2, timeout_seconds=5)

        for i in range(len(coords)):
            for j in range(len(coords)):
                assert abs(single[i][j] - chunked[i][j]) < 1.0  # tolerancia de redondeo

    def test_rejects_coords_with_swapped_lat_lon(self):
        """Bug real: coordenadas con ejes lat/lon invertidos (error común de
        import/integración) caen dentro del rango numérico válido por
        coincidencia y pasan _validate_coords_are_geographic — pero OSRM las
        interpreta como un punto sin cobertura real y las "snapea" a un nodo
        cualquiera a miles de km, devolviendo una matriz de distancia-cero
        sintácticamente válida pero sin sentido, sin ningún error visible.
        Con lon/lat invertido a lat/lon (Lima con orden (-12.05,-77.04) en vez
        de (-77.04,-12.05)), debe rechazarse por snap-distance absurda."""
        swapped_coords = [(-12.05, -77.04), (-12.06, -77.05)]
        with pytest.raises(OSRMError, match="snapped"):
            get_osrm_matrix(
                swapped_coords,
                base_url=os.getenv("OSRM_URL"),
                max_table_size=100,
                timeout_seconds=5,
            )
