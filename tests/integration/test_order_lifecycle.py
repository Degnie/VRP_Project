"""
Tests de integración para el ciclo de vida de pedido (Etapa 4):
estado de entrega, asignación repartidor↔vehículo, my-route, reschedule.
"""

import os
import uuid

import pytest

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None
MONGO_AVAILABLE = os.getenv("MONGO_URL") is not None


@pytest.mark.skipif(not (POSTGRES_AVAILABLE and MONGO_AVAILABLE), reason="PostgreSQL/MongoDB not configured")
class TestOrderLifecycle:
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
        token = login.json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        return token, me.json()["id"]

    def _solve_instance(self, client, token, instancia_id, num_vehicles=1):
        return client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20)],
                "demands": [10, 10],
                "num_vehicles": num_vehicles,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    def _assign(self, client, owner_token, instancia_id, assignments):
        return client.put(
            f"/instances/{instancia_id}/assignments",
            json={"assignments": assignments},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

    def test_owner_can_update_delivery_status(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle A")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "entregado"

    def test_invalid_status_rejected(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle B")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "volando"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 422

    def test_repartidor_without_assignment_cannot_update_status(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle C")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 403

    def test_repartidor_can_update_status_of_own_route(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle D")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200

    def test_repartidor_cannot_set_assignments(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle E")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = self._assign(client, repartidor_token, instancia_id, {"0": repartidor_id})
        assert response.status_code == 403

    def test_my_route_returns_stops_with_status(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle F")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        response = client.get(
            f"/instances/{instancia_id}/my-route",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["vehicle_id"] == 0
        assert len(data["stops"]) == 2
        assert all(stop["delivery_status"] == "pendiente" for stop in data["stops"])

    def test_my_route_404_without_assignment(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle G")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.get(
            f"/instances/{instancia_id}/my-route",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 404

    def test_reschedule_creates_new_instance_with_pending_only(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle H")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        # Marcar cliente 1 como entregado — solo el 2 debe reprogramarse.
        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rescheduled_client_ids"] == [2]

        new_instances = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"})
        assert data["new_instancia_id"] in [i["id"] for i in new_instances.json()]

    def test_reschedule_with_no_pending_returns_400(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle I")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        for cliente_id in (1, 2):
            client.put(
                f"/instances/{instancia_id}/clients/{cliente_id}/status",
                json={"status": "entregado"},
                headers={"Authorization": f"Bearer {owner_token}"},
            )

        response = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 400

    def test_status_update_isolated_between_accounts(self):
        client = self._client()
        token_a = self._register_owner(client, "Lifecycle J")
        token_b = self._register_owner(client, "Lifecycle K")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, token_a, instancia_id)

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404
