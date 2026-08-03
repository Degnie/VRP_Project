"""
Tests de integración para /coverage-zone: reemplaza (no acumula), aislado
por cuenta, permisos por rol.
"""

import os
import uuid

import pytest
from backend_python import config as _config  # noqa: F401

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestCoverageZoneAPI:
    """spec: CU-COV-001, RN-COV-001

    RN-COV-003: spec: RN-COV-003 — PENDIENTE. La regla vive enteramente en
    frontend/src/components/InstanceForm.tsx (updateGroupField recalcula
    inCoverage al editar X/Y) — no hay endpoint ni lógica de backend que
    cubra. El repo no tiene test runner de frontend en `make verify` (mismo
    gap documentado para el fix de RepartidorView.tsx, Ronda 1 del ciclo 2);
    verificado con `tsc -b` (sin errores nuevos) y revisión manual del flujo.
    """

    def _client(self):
        from fastapi.testclient import TestClient
        from backend_python.api import create_app
        return TestClient(create_app())

    def _register_owner(self, client, account_name: str):
        email = f"owner-{uuid.uuid4().hex[:8]}@test.local"
        response = client.post("/auth/register", json={
            "account_name": account_name, "email": email, "password": "clave123",
        })
        return response.json()["access_token"]

    def _register_repartidor(self, client, owner_token: str):
        email = f"repa-{uuid.uuid4().hex[:8]}@test.local"
        client.post(
            "/auth/users",
            json={"email": email, "password": "clave123", "role": "repartidor"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        login = client.post("/auth/login", json={"email": email, "password": "clave123"})
        return login.json()["access_token"]

    def test_get_empty_zone_returns_null(self):
        client = self._client()
        token = self._register_owner(client, "Cobertura A")
        response = client.get("/coverage-zone", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() is None

    def test_put_then_get_returns_points(self):
        client = self._client()
        token = self._register_owner(client, "Cobertura B")
        headers = {"Authorization": f"Bearer {token}"}

        points = [[-77.03, -12.03], [-77.00, -12.03], [-77.00, -12.00]]
        put_response = client.put("/coverage-zone", json={"points": points}, headers=headers)
        assert put_response.status_code == 200

        get_response = client.get("/coverage-zone", headers=headers)
        assert get_response.json()["points"] == points

    def test_put_replaces_not_accumulates(self):
        client = self._client()
        token = self._register_owner(client, "Cobertura C")
        headers = {"Authorization": f"Bearer {token}"}

        client.put("/coverage-zone", json={
            "points": [[-77.03, -12.03], [-77.00, -12.03], [-77.00, -12.00]]
        }, headers=headers)
        second_points = [[-76.99, -12.02], [-76.98, -12.02], [-76.98, -12.00]]
        client.put("/coverage-zone", json={"points": second_points}, headers=headers)

        get_response = client.get("/coverage-zone", headers=headers)
        assert get_response.json()["points"] == second_points

    def test_repartidor_cannot_write_zone(self):
        client = self._client()
        owner_token = self._register_owner(client, "Cobertura D")
        repartidor_token = self._register_repartidor(client, owner_token)

        response = client.put(
            "/coverage-zone",
            json={"points": [[-77.03, -12.03], [-77.00, -12.03], [-77.00, -12.00]]},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 403

    def test_repartidor_can_read_zone(self):
        client = self._client()
        owner_token = self._register_owner(client, "Cobertura E")
        repartidor_token = self._register_repartidor(client, owner_token)

        client.put(
            "/coverage-zone",
            json={"points": [[-77.03, -12.03], [-77.00, -12.03], [-77.00, -12.00]]},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        response = client.get("/coverage-zone", headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 200
        assert len(response.json()["points"]) == 3

    def test_put_rejects_fewer_than_3_points(self):
        """spec: RN-COV-002"""
        client = self._client()
        token = self._register_owner(client, "Cobertura H")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.put(
            "/coverage-zone",
            json={"points": [[-77.03, -12.03], [-77.00, -12.03]]},
            headers=headers,
        )
        assert response.status_code == 422

    def test_put_rejects_coordinate_out_of_range(self):
        """spec: RN-COV-002"""
        client = self._client()
        token = self._register_owner(client, "Cobertura I")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.put(
            "/coverage-zone",
            json={"points": [[200.0, -12.03], [-77.00, -12.03], [-77.00, -12.00]]},
            headers=headers,
        )
        assert response.status_code == 422

    def test_zone_isolated_between_accounts(self):
        client = self._client()
        token_a = self._register_owner(client, "Cobertura F")
        token_b = self._register_owner(client, "Cobertura G")

        client.put(
            "/coverage-zone",
            json={"points": [[-77.03, -12.03], [-77.00, -12.03], [-77.00, -12.00]]},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        response = client.get("/coverage-zone", headers={"Authorization": f"Bearer {token_b}"})
        assert response.json() is None
