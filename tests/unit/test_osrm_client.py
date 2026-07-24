"""
Tests para el cliente OSRM: matriz simple, chunking, y propagación de errores.
Se activan solo si OSRM_URL está configurado y el servicio responde (mismo
patrón skipif que test_persistence.py para Postgres/Mongo).
"""

import os
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
