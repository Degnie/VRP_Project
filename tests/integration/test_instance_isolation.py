"""
Tests de integración: /solve, /instances, /solutions/{id} exigen auth y
aíslan instancias por cuenta (Etapa 2).
"""

import os
import uuid

import pytest

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None
MONGO_AVAILABLE = os.getenv("MONGO_URL") is not None


@pytest.mark.skipif(not (POSTGRES_AVAILABLE and MONGO_AVAILABLE), reason="PostgreSQL/MongoDB not configured")
class TestInstanceIsolation:
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

    def test_solve_without_token_rejected(self):
        client = self._client()
        response = client.post("/solve", json={
            "instancia_id": "no-auth", "coordinates": [(0, 0), (1, 1)],
            "demands": [5], "num_vehicles": 1, "vehicle_capacity": 50,
        })
        assert response.status_code == 401

    def test_repartidor_cannot_solve(self):
        client = self._client()
        owner_token = self._register_owner(client, "Solve Roles A")
        repartidor_token = self._register_repartidor(client, owner_token)

        response = self._solve_instance(client, repartidor_token, f"repa-solve-{uuid.uuid4().hex[:6]}")
        assert response.status_code == 403

    def test_instances_isolated_between_accounts(self):
        client = self._client()
        token_a = self._register_owner(client, "Isolation A")
        token_b = self._register_owner(client, "Isolation B")

        instancia_id = f"isolated-{uuid.uuid4().hex[:8]}"
        solve_response = self._solve_instance(client, token_a, instancia_id)
        assert solve_response.status_code == 200

        list_a = client.get("/instances", headers={"Authorization": f"Bearer {token_a}"})
        list_b = client.get("/instances", headers={"Authorization": f"Bearer {token_b}"})
        assert instancia_id in [i["id"] for i in list_a.json()]
        assert instancia_id not in [i["id"] for i in list_b.json()]

    def test_solution_not_visible_to_other_account(self):
        client = self._client()
        token_a = self._register_owner(client, "Isolation C")
        token_b = self._register_owner(client, "Isolation D")

        instancia_id = f"isolated-sol-{uuid.uuid4().hex[:8]}"
        assert self._solve_instance(client, token_a, instancia_id).status_code == 200

        own_solution = client.get(f"/solutions/{instancia_id}", headers={"Authorization": f"Bearer {token_a}"})
        assert own_solution.status_code == 200

        other_solution = client.get(f"/solutions/{instancia_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert other_solution.status_code == 404

    def test_solutions_require_auth(self):
        client = self._client()
        response = client.get("/solutions/anything")
        assert response.status_code == 401
