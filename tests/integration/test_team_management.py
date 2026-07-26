"""
Tests de integración para gestión de equipo (Etapa A): listar equipo,
activar/desactivar usuarios.
"""

import os
import uuid

import pytest
from backend_python import config as _config  # noqa: F401  (triggers .env.local load)

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestTeamManagement:
    def _client(self):
        from fastapi.testclient import TestClient
        from backend_python.api import create_app
        return TestClient(create_app())

    def _unique_email(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}@test.local"

    def _register_owner(self, client, account_name: str):
        email = self._unique_email("owner")
        response = client.post("/auth/register", json={
            "account_name": account_name, "email": email, "password": "clave123",
        })
        return response.json()["access_token"]

    def _create_member(self, client, owner_token: str, role: str):
        email = self._unique_email(role)
        response = client.post(
            "/auth/users",
            json={"email": email, "password": "clave123", "role": role},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        return response.json()["id"], email

    def test_list_team_requires_auth(self):
        client = self._client()
        response = client.get("/auth/users")
        assert response.status_code == 401

    def test_repartidor_cannot_list_team(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team A")
        repa_id, repa_email = self._create_member(client, owner_token, "repartidor")
        login = client.post("/auth/login", json={"email": repa_email, "password": "clave123"})
        repa_token = login.json()["access_token"]

        response = client.get("/auth/users", headers={"Authorization": f"Bearer {repa_token}"})
        assert response.status_code == 403

    def test_owner_lists_team_includes_self_and_invited(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team B")
        self._create_member(client, owner_token, "operario")
        self._create_member(client, owner_token, "repartidor")

        response = client.get("/auth/users", headers={"Authorization": f"Bearer {owner_token}"})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 3
        roles = sorted(m["role"] for m in body)
        assert roles == ["dueño", "operario", "repartidor"]
        assert all(m["active"] for m in body)

    def test_team_isolated_between_accounts(self):
        client = self._client()
        token_a = self._register_owner(client, "Team C")
        token_b = self._register_owner(client, "Team D")
        self._create_member(client, token_a, "operario")

        list_a = client.get("/auth/users", headers={"Authorization": f"Bearer {token_a}"})
        list_b = client.get("/auth/users", headers={"Authorization": f"Bearer {token_b}"})
        assert len(list_a.json()) == 2  # dueño + operario invitado
        assert len(list_b.json()) == 1  # solo el dueño de la cuenta B

    def test_owner_deactivates_member(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team E")
        repa_id, _ = self._create_member(client, owner_token, "repartidor")

        response = client.patch(
            f"/auth/users/{repa_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json()["active"] is False

    def test_deactivated_user_cannot_login(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team F")
        repa_id, repa_email = self._create_member(client, owner_token, "repartidor")

        client.patch(
            f"/auth/users/{repa_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        login = client.post("/auth/login", json={"email": repa_email, "password": "clave123"})
        assert login.status_code == 401

    def test_deactivated_user_existing_token_immediately_rejected(self):
        """Bug real: un usuario desactivado seguía teniendo acceso completo
        con su token ya emitido hasta que expirara solo (hasta 8hs, un turno
        completo) — get_current_user solo decodificaba el JWT sin volver a
        chequear el estado 'active' en la base."""
        client = self._client()
        owner_token = self._register_owner(client, "Team Revoke")
        repa_id, repa_email = self._create_member(client, owner_token, "repartidor")
        login = client.post("/auth/login", json={"email": repa_email, "password": "clave123"})
        repa_token = login.json()["access_token"]

        # El token todavía es válido y funciona antes de la desactivación.
        before = client.get("/auth/me", headers={"Authorization": f"Bearer {repa_token}"})
        assert before.status_code == 200

        client.patch(
            f"/auth/users/{repa_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        # El MISMO token, ya emitido, debe dejar de funcionar de inmediato —
        # no hace falta esperar a que expire ni volver a loguear.
        after = client.get("/auth/me", headers={"Authorization": f"Bearer {repa_token}"})
        assert after.status_code == 401

    def test_owner_cannot_deactivate_self(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team G")
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        owner_id = me.json()["id"]

        response = client.patch(
            f"/auth/users/{owner_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 400

    def test_repartidor_cannot_deactivate_anyone(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team H")
        repa_id, repa_email = self._create_member(client, owner_token, "repartidor")
        login = client.post("/auth/login", json={"email": repa_email, "password": "clave123"})
        repa_token = login.json()["access_token"]

        response = client.patch(
            f"/auth/users/{repa_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {repa_token}"},
        )
        assert response.status_code == 403

    def test_operario_cannot_deactivate_owner(self):
        """Bug real: un operario podía desactivar al dueño de la cuenta vía
        PATCH /auth/users/{owner_id}, dejando la pyme sin nadie con acceso si
        era el único dueño — sin ninguna verificación de jerarquía de roles."""
        client = self._client()
        owner_token = self._register_owner(client, "Team K")
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        owner_id = me.json()["id"]
        operario_id, operario_email = self._create_member(client, owner_token, "operario")
        login = client.post("/auth/login", json={"email": operario_email, "password": "clave123"})
        operario_token = login.json()["access_token"]

        response = client.patch(
            f"/auth/users/{owner_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {operario_token}"},
        )
        assert response.status_code == 403

        # El dueño sigue pudiendo loguear normalmente.
        me_check = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        assert me_check.status_code == 200

    def test_operario_deactivating_owner_of_other_account_gets_404_not_403(self):
        """El chequeo de jerarquía (403 'solo un dueño puede desactivar a otro
        dueño') no debe filtrar si un user_id corresponde a un dueño de OTRA
        cuenta — eso revela metadatos de una cuenta ajena. Debe comportarse
        igual que cualquier user_id que no pertenece a la cuenta: 404."""
        client = self._client()
        token_a = self._register_owner(client, "Team L")
        token_b = self._register_owner(client, "Team M")
        operario_id, operario_email = self._create_member(client, token_a, "operario")
        login = client.post("/auth/login", json={"email": operario_email, "password": "clave123"})
        operario_token = login.json()["access_token"]

        me_b = client.get("/auth/me", headers={"Authorization": f"Bearer {token_b}"})
        owner_b_id = me_b.json()["id"]

        response = client.patch(
            f"/auth/users/{owner_b_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {operario_token}"},
        )
        assert response.status_code == 404

    def test_cannot_deactivate_user_from_other_account(self):
        client = self._client()
        token_a = self._register_owner(client, "Team I")
        token_b = self._register_owner(client, "Team J")
        repa_id, _ = self._create_member(client, token_a, "repartidor")

        response = client.patch(
            f"/auth/users/{repa_id}",
            json={"active": False},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404

    def test_concurrent_register_same_email_never_returns_500(self):
        """Bug real (TOCTOU): register() chequeaba get_user_by_email() y
        recién después insertaba — dos registros con el mismo email casi
        simultáneos podían pasar ambos el chequeo antes de que cualquiera
        insertara, y el segundo terminaba en un 500 genérico en vez de 400."""
        import threading

        client = self._client()
        email = self._unique_email("race")
        results = []
        results_lock = threading.Lock()

        def do_register():
            res = client.post("/auth/register", json={
                "account_name": "Race Co", "email": email, "password": "clave123",
            })
            with results_lock:
                results.append(res)

        threads = [threading.Thread(target=do_register) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        statuses = sorted(r.status_code for r in results)
        assert 200 in statuses
        assert all(s in (200, 400) for s in statuses)  # nunca 500
        assert statuses.count(200) == 1

    def test_register_rejects_email_over_max_length(self):
        client = self._client()
        long_email = "a" * 250 + "@test.local"  # > 255 chars

        response = client.post("/auth/register", json={
            "account_name": "Long Email Co", "email": long_email, "password": "clave123",
        })
        assert response.status_code == 422

    def test_concurrent_create_vehicle_catalog_same_id_never_returns_500(self):
        """Bug real (mismo patrón TOCTOU que el email): el id de un tipo de
        vehículo es opcional y lo genera el cliente para UI optimista — un
        reintento de red normal (o doble click) puede reenviar el mismo POST
        con el mismo id antes de recibir la respuesta del primero, chocando
        contra la PK y devolviendo 500 en vez de un 409 claro."""
        import threading
        import uuid as uuid_module

        client = self._client()
        owner_token = self._register_owner(client, "Team Vehicle Race")
        shared_id = str(uuid_module.uuid4())

        results = []
        results_lock = threading.Lock()

        def do_create():
            res = client.post("/vehicle-catalog", json={
                "id": shared_id, "name": "Camioneta", "weight_capacity_kg": 300,
                "volume_capacity_m3": 2.5, "tolerance_margin": 0.9,
            }, headers={"Authorization": f"Bearer {owner_token}"})
            with results_lock:
                results.append(res)

        threads = [threading.Thread(target=do_create) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        statuses = sorted(r.status_code for r in results)
        assert 201 in statuses
        assert all(s in (201, 409) for s in statuses)  # nunca 500
        assert statuses.count(201) == 1

    def test_create_vehicle_type_rejects_name_over_max_length(self):
        client = self._client()
        owner_token = self._register_owner(client, "Team Long Name")

        response = client.post("/vehicle-catalog", json={
            "name": "x" * 300, "weight_capacity_kg": 100,
            "volume_capacity_m3": 1, "tolerance_margin": 0.9,
        }, headers={"Authorization": f"Bearer {owner_token}"})
        assert response.status_code == 422
