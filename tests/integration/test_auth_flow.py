"""
Tests de integración del flujo de auth completo: register → login → users,
contra los endpoints reales de FastAPI (TestClient) y Postgres real.
"""

import os
import uuid

import pytest
from backend_python import config as _config  # noqa: F401  (triggers .env.local load)

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestAuthFlow:
    def _client(self):
        from fastapi.testclient import TestClient
        from backend_python.api import create_app
        return TestClient(create_app())

    def _unique_email(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}@test.local"

    def test_register_creates_account_and_owner(self):
        client = self._client()
        email = self._unique_email("dueno")
        response = client.post("/auth/register", json={
            "account_name": "Empresa de Prueba",
            "email": email,
            "password": "clave-segura-123",
            "full_name": "Dueño de Prueba",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["role"] == "dueño"
        assert "access_token" in body

    def test_register_rejects_short_password(self):
        """Bug real (Ronda 21, ciclo nuevo, dueño): no había ninguna longitud
        mínima de contraseña en todo el stack — un dueño podía crear su
        cuenta de negocio con una contraseña de un solo carácter."""
        client = self._client()
        response = client.post("/auth/register", json={
            "account_name": "Empresa Corta",
            "email": self._unique_email("cortapass"),
            "password": "1234567",  # 7 chars, por debajo del mínimo de 8
        })
        assert response.status_code == 422

    def test_create_user_rejects_short_password(self):
        client = self._client()
        owner_token = self._client_register_owner()

        response = client.post(
            "/auth/users",
            json={"email": self._unique_email("repacorta"), "password": "abc", "role": "repartidor"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 422

    def _client_register_owner(self) -> str:
        client = self._client()
        response = client.post("/auth/register", json={
            "account_name": "Empresa Owner Helper",
            "email": self._unique_email("ownerhelper"),
            "password": "clave-segura-123",
        })
        return response.json()["access_token"]

    def test_register_duplicate_email_rejected(self):
        client = self._client()
        email = self._unique_email("dup")
        payload = {"account_name": "A", "email": email, "password": "clave123"}
        first = client.post("/auth/register", json=payload)
        assert first.status_code == 200

        second = client.post("/auth/register", json=payload)
        assert second.status_code == 400

    def test_register_leaves_no_orphaned_account_if_user_insert_fails(self):
        """Bug real (Ronda 2, ciclo nuevo, dueño): create_account() y
        create_user() eran dos escrituras independientes con su propio
        commit — si la segunda fallaba por cualquier motivo que no fuera el
        email duplicado (ya capturado aparte), la cuenta quedaba huérfana
        sin usuario, sin ningún endpoint para detectarla o recuperarla.
        Se fuerza el fallo en el SEGUNDO INSERT (el de users) dentro de la
        misma transacción, para probar que el rollback deshace también el
        primero (el de accounts) — no alcanza con mockear el método entero."""
        from unittest.mock import patch
        from backend_python.persistence.postgres_adapter import psycopg2, PostgreSQLAdapter

        client = self._client()
        email = self._unique_email("orphan")
        payload = {"account_name": "Cuenta Huérfana", "email": email, "password": "clave123"}

        def failing_after_account_insert(self, account_id, account_name, user_id, email_, password_hash, role, full_name=None):
            cursor = self.conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO accounts (id, name) VALUES (%s, %s)",
                    [account_id, account_name],
                )
                raise psycopg2.Error("simulated failure on users insert")
            except psycopg2.Error:
                self.conn.rollback()
                raise
            finally:
                cursor.close()

        with patch.object(PostgreSQLAdapter, "create_account_with_user", failing_after_account_insert):
            response = client.post("/auth/register", json=payload)
        assert response.status_code == 500

        # Si el rollback deshizo también el INSERT de accounts, reintentar
        # con el MISMO email (sin mock) debe crear todo limpio de nuevo.
        retry = client.post("/auth/register", json=payload)
        assert retry.status_code == 200

    def test_login_correct_credentials(self):
        client = self._client()
        email = self._unique_email("login")
        client.post("/auth/register", json={
            "account_name": "B", "email": email, "password": "clave123",
        })

        response = client.post("/auth/login", json={"email": email, "password": "clave123"})
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_incorrect_credentials(self):
        client = self._client()
        email = self._unique_email("badlogin")
        client.post("/auth/register", json={
            "account_name": "C", "email": email, "password": "clave123",
        })

        response = client.post("/auth/login", json={"email": email, "password": "incorrecta"})
        assert response.status_code == 401

    def test_create_user_requires_token(self):
        client = self._client()
        response = client.post("/auth/users", json={
            "email": self._unique_email("nouser"), "password": "x", "role": "repartidor",
        })
        assert response.status_code == 403 or response.status_code == 401

    def test_create_user_repartidor_forbidden(self):
        client = self._client()
        owner_email = self._unique_email("owner")
        register = client.post("/auth/register", json={
            "account_name": "D", "email": owner_email, "password": "clave123",
        })
        owner_token = register.json()["access_token"]

        repartidor_email = self._unique_email("repa")
        created = client.post(
            "/auth/users",
            json={"email": repartidor_email, "password": "clave123", "role": "repartidor"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert created.status_code == 201

        repartidor_login = client.post(
            "/auth/login", json={"email": repartidor_email, "password": "clave123"}
        )
        repartidor_token = repartidor_login.json()["access_token"]

        forbidden = client.post(
            "/auth/users",
            json={"email": self._unique_email("x"), "password": "y", "role": "repartidor"},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert forbidden.status_code == 403

    def test_owner_can_create_users(self):
        client = self._client()
        owner_email = self._unique_email("owner2")
        register = client.post("/auth/register", json={
            "account_name": "E", "email": owner_email, "password": "clave123",
        })
        owner_token = register.json()["access_token"]

        response = client.post(
            "/auth/users",
            json={"email": self._unique_email("op"), "password": "clave123", "role": "operario"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 201
        assert response.json()["role"] == "operario"

    def test_list_team_respects_limit_and_offset(self):
        """Bug real (Ronda 2, ciclo nuevo, dueño): GET /auth/users no
        aceptaba limit/offset — una cuenta con muchos usuarios no tenía
        forma de acotar la respuesta."""
        client = self._client()
        owner_email = self._unique_email("owner-page")
        register = client.post("/auth/register", json={
            "account_name": "Equipo Paginado", "email": owner_email, "password": "clave123",
        })
        owner_token = register.json()["access_token"]

        for _ in range(2):
            client.post(
                "/auth/users",
                json={"email": self._unique_email("op"), "password": "clave123", "role": "operario"},
                headers={"Authorization": f"Bearer {owner_token}"},
            )

        # 3 usuarios en total: el dueño + 2 operarios.
        page1 = client.get(
            "/auth/users", params={"limit": 2}, headers={"Authorization": f"Bearer {owner_token}"}
        )
        assert page1.status_code == 200
        assert len(page1.json()) == 2

        assert client.get(
            "/auth/users", params={"limit": 0}, headers={"Authorization": f"Bearer {owner_token}"}
        ).status_code == 422
