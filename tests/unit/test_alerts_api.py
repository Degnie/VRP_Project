"""
Tests de integración para /alerts: el repartidor notifica al dueño/operador
("No encuentro la dirección") sobre un cliente específico de una instancia
en curso. Notificación por polling (tabla en Postgres + GET), sin
websockets — ver docs/delta-actual.md, decisión aceptada para RN-024.

spec: RN-024
"""

import os
import uuid

import pytest
from backend_python import config as _config  # noqa: F401

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestAlertsAPI:
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

    def _register_repartidor(self, client, owner_token: str):
        email = f"repa-{uuid.uuid4().hex[:8]}@test.local"
        client.post(
            "/auth/users",
            json={"email": email, "password": "clave123", "role": "repartidor"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        login = client.post("/auth/login", json={"email": email, "password": "clave123"})
        return login.json()["access_token"]

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

    def test_repartidor_can_create_alert(self):
        client = self._client()
        owner_token, _ = self._register_owner(client, "Alertas Crear")
        repartidor_token = self._register_repartidor(client, owner_token)
        instancia_id = f"al-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.post("/alerts", json={
            "instancia_id": instancia_id, "cliente_id": 1,
            "motivo": "No encuentro la dirección",
        }, headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 201
        assert response.json()["motivo"] == "No encuentro la dirección"
        assert response.json()["resuelta"] is False

    def test_owner_can_list_alerts_of_account(self):
        client = self._client()
        owner_token, _ = self._register_owner(client, "Alertas Listar")
        repartidor_token = self._register_repartidor(client, owner_token)
        instancia_id = f"al-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        client.post("/alerts", json={
            "instancia_id": instancia_id, "cliente_id": 1,
            "motivo": "No encuentro la dirección",
        }, headers={"Authorization": f"Bearer {repartidor_token}"})

        listed = client.get("/alerts", headers={"Authorization": f"Bearer {owner_token}"})
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["cliente_id"] == 1

    def test_alerts_isolated_between_accounts(self):
        client = self._client()
        owner_a_token, _ = self._register_owner(client, "Alertas Cuenta A")
        repartidor_a_token = self._register_repartidor(client, owner_a_token)
        instancia_id = f"al-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_a_token, instancia_id)
        client.post("/alerts", json={
            "instancia_id": instancia_id, "cliente_id": 1, "motivo": "No encuentro",
        }, headers={"Authorization": f"Bearer {repartidor_a_token}"})

        owner_b_token, _ = self._register_owner(client, "Alertas Cuenta B")
        listed_b = client.get("/alerts", headers={"Authorization": f"Bearer {owner_b_token}"})
        assert listed_b.json() == []

    def test_dueno_or_operario_required_to_list_alerts(self):
        client = self._client()
        owner_token, _ = self._register_owner(client, "Alertas Rol")
        repartidor_token = self._register_repartidor(client, owner_token)

        response = client.get("/alerts", headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 403

    def test_create_alert_requires_repartidor_role(self):
        """Un dueño/operario no necesita crear alertas — el flujo es
        repartidor → dueño/operario, no al revés."""
        client = self._client()
        owner_token, _ = self._register_owner(client, "Alertas RolCrear")
        instancia_id = f"al-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.post("/alerts", json={
            "instancia_id": instancia_id, "cliente_id": 1, "motivo": "No encuentro",
        }, headers={"Authorization": f"Bearer {owner_token}"})
        assert response.status_code == 403
