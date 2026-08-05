"""
Tests de integración para GET /dashboard: panel agregado por fecha para el
dueño — distancia recorrida, entregas realizadas, vehículos utilizados y
vehículos disponibles, agrupado por la fecha de creación (created_at) de
cada instancia (ver docs/delta-actual.md, decisión aceptada para RN-023).

spec: RN-023
"""

import os
import uuid
from datetime import date

import pytest
from backend_python import config as _config  # noqa: F401

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None
MONGO_AVAILABLE = os.getenv("MONGO_URL") is not None


@pytest.mark.skipif(
    not (POSTGRES_AVAILABLE and MONGO_AVAILABLE), reason="PostgreSQL and MongoDB not configured"
)
class TestDashboardAPI:
    def _client(self):
        from fastapi.testclient import TestClient
        from backend_python.api import create_app
        return TestClient(create_app())

    def _register_owner(self, client, account_name: str):
        email = f"owner-{uuid.uuid4().hex[:8]}@test.local"
        response = client.post("/auth/register", json={
            "account_name": account_name, "email": email, "password": "clave123",
        })
        return response.json()["access_token"], response.json()["account_id"]

    def _solve_instance(self, client, token, instancia_id):
        return client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20)],
                "demands": [10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_dashboard_returns_today_summary_by_default(self):
        client = self._client()
        token, _ = self._register_owner(client, "Dashboard Hoy")
        instancia_id = f"dash-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, token, instancia_id)

        response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        body = response.json()
        assert body["fecha"] == date.today().isoformat()
        assert body["num_entregas"] >= 0
        assert body["distancia_total"] >= 0
        assert body["vehiculos_utilizados"] >= 1

    def test_dashboard_counts_delivered_clients(self):
        client = self._client()
        token, _ = self._register_owner(client, "Dashboard Entregas")
        instancia_id = f"dash-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, token, instancia_id)

        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert response.json()["num_entregas"] >= 1

    def test_dashboard_accepts_explicit_date_query_param(self):
        client = self._client()
        token, _ = self._register_owner(client, "Dashboard Fecha Explicita")

        response = client.get(
            "/dashboard", params={"date": "2020-01-01"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["fecha"] == "2020-01-01"
        # Ninguna instancia creada ese día — agregados en cero, no error.
        assert response.json()["num_entregas"] == 0

    def test_dashboard_isolated_between_accounts(self):
        client = self._client()
        token_a, _ = self._register_owner(client, "Dashboard Cuenta A")
        instancia_id = f"dash-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, token_a, instancia_id)
        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {token_a}"},
        )

        token_b, _ = self._register_owner(client, "Dashboard Cuenta B")
        response_b = client.get("/dashboard", headers={"Authorization": f"Bearer {token_b}"})
        assert response_b.json()["num_entregas"] == 0

    def test_dashboard_requires_dueno_or_operario(self):
        client = self._client()
        owner_token, _ = self._register_owner(client, "Dashboard Rol")
        email = f"repa-{uuid.uuid4().hex[:8]}@test.local"
        client.post(
            "/auth/users",
            json={"email": email, "password": "clave123", "role": "repartidor"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        login = client.post("/auth/login", json={"email": email, "password": "clave123"})
        repartidor_token = login.json()["access_token"]

        response = client.get("/dashboard", headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 403
