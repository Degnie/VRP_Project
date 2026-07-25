"""
Tests de integración para /vehicle-catalog: CRUD aislado por cuenta,
permisos por rol.
"""

import os
import uuid

import pytest
from backend_python import config as _config  # noqa: F401

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestVehicleCatalogAPI:
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

    def test_create_and_list_vehicle_type(self):
        client = self._client()
        token, _ = self._register_owner(client, "Flota A")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 30, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers=headers)
        assert created.status_code == 201

        listed = client.get("/vehicle-catalog", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["name"] == "Moto"

    def test_catalog_isolated_between_accounts(self):
        client = self._client()
        token_a, _ = self._register_owner(client, "Flota B")
        token_b, _ = self._register_owner(client, "Flota C")

        client.post("/vehicle-catalog", json={
            "name": "Camioneta", "weight_capacity_kg": 600, "volume_capacity_m3": 3.5, "tolerance_margin": 0.9,
        }, headers={"Authorization": f"Bearer {token_a}"})

        listed_b = client.get("/vehicle-catalog", headers={"Authorization": f"Bearer {token_b}"})
        assert listed_b.json() == []

    def test_repartidor_cannot_write_catalog(self):
        client = self._client()
        owner_token, _ = self._register_owner(client, "Flota D")
        repartidor_token = self._register_repartidor(client, owner_token)

        response = client.post("/vehicle-catalog", json={
            "name": "Auto", "weight_capacity_kg": 150, "volume_capacity_m3": 0.6, "tolerance_margin": 0.9,
        }, headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 403

    def test_repartidor_can_read_catalog(self):
        client = self._client()
        owner_token, _ = self._register_owner(client, "Flota E")
        repartidor_token = self._register_repartidor(client, owner_token)

        client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 30, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers={"Authorization": f"Bearer {owner_token}"})

        response = client.get("/vehicle-catalog", headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_update_and_delete_vehicle_type(self):
        client = self._client()
        token, _ = self._register_owner(client, "Flota F")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 30, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers=headers)
        vehicle_id = created.json()["id"]

        updated = client.put(f"/vehicle-catalog/{vehicle_id}", json={
            "name": "Moto Grande", "weight_capacity_kg": 50, "volume_capacity_m3": 0.2, "tolerance_margin": 0.85,
        }, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["name"] == "Moto Grande"

        deleted = client.delete(f"/vehicle-catalog/{vehicle_id}", headers=headers)
        assert deleted.status_code == 204

        listed = client.get("/vehicle-catalog", headers=headers)
        assert listed.json() == []
