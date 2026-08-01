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

    def test_create_respects_client_provided_id(self):
        """Bug real: el backend siempre generaba su propio id (uuid4),
        ignorando cualquier id enviado por el cliente. El frontend arma la
        fila con un id local (crypto.randomUUID()) de forma optimista antes
        de que el POST termine — si la respuesta traía un id distinto, el
        snapshot stale de esa respuesta terminaba pisando cualquier edición
        hecha mientras la request estaba en vuelo (nombre truncado al
        escribir rápido). Ahora el backend debe respetar el id del cliente."""
        client = self._client()
        token, _ = self._register_owner(client, "Flota IdClient")
        headers = {"Authorization": f"Bearer {token}"}
        client_id = str(uuid.uuid4())

        created = client.post("/vehicle-catalog", json={
            "id": client_id, "name": "Camioneta", "weight_capacity_kg": 300,
            "volume_capacity_m3": 2.5, "tolerance_margin": 0.9,
        }, headers=headers)
        assert created.status_code == 201
        assert created.json()["id"] == client_id

        listed = client.get("/vehicle-catalog", headers=headers)
        assert listed.json()[0]["id"] == client_id

    def test_create_without_id_still_generates_one(self):
        client = self._client()
        token, _ = self._register_owner(client, "Flota SinId")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 30, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers=headers)
        assert created.status_code == 201
        assert created.json()["id"]

    def test_create_vehicle_type_zero_weight_gives_spanish_error(self):
        """Bug real (Ronda 18, ciclo nuevo, dueño): weight_capacity_kg/
        volume_capacity_m3 usaban Field(gt=0) sin validador propio, dejando
        pasar el mensaje crudo de Pydantic ("Input should be greater than
        0", en inglés) hasta la UI — único texto en inglés en una app con
        más de 60 mensajes ya traducidos con tono consistente."""
        client = self._client()
        token, _ = self._register_owner(client, "Flota ZeroWeight")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 0, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers=headers)
        assert response.status_code == 422
        detail = str(response.json()["detail"])
        assert "Input should be greater than" not in detail
        assert "mayor a 0" in detail

    def test_create_vehicle_type_zero_volume_gives_spanish_error(self):
        client = self._client()
        token, _ = self._register_owner(client, "Flota ZeroVolume")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 30, "volume_capacity_m3": 0, "tolerance_margin": 0.9,
        }, headers=headers)
        assert response.status_code == 422
        detail = str(response.json()["detail"])
        assert "Input should be greater than" not in detail
        assert "mayor a 0" in detail

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

    def test_create_rejects_non_positive_capacity(self):
        """Bug real (Ronda 35, operario): capacidad 0/negativa se persistía
        sin error y solo fallaba, de forma opaca, recién al resolver una
        instancia con ese vehículo seleccionado."""
        client = self._client()
        token, _ = self._register_owner(client, "Flota Cap0")
        headers = {"Authorization": f"Bearer {token}"}

        for bad_weight, bad_volume in [(0, 0.15), (-10, 0.15), (30, 0), (30, -1)]:
            response = client.post("/vehicle-catalog", json={
                "name": "Moto", "weight_capacity_kg": bad_weight,
                "volume_capacity_m3": bad_volume, "tolerance_margin": 0.9,
            }, headers=headers)
            assert response.status_code == 422

        listed = client.get("/vehicle-catalog", headers=headers)
        assert listed.json() == []

    def test_update_rejects_non_positive_capacity(self):
        client = self._client()
        token, _ = self._register_owner(client, "Flota Cap0Upd")
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/vehicle-catalog", json={
            "name": "Moto", "weight_capacity_kg": 30, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers=headers)
        vehicle_id = created.json()["id"]

        updated = client.put(f"/vehicle-catalog/{vehicle_id}", json={
            "name": "Moto", "weight_capacity_kg": 0, "volume_capacity_m3": 0.15, "tolerance_margin": 0.9,
        }, headers=headers)
        assert updated.status_code == 422
