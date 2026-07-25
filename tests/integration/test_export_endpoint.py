"""Tests de integración para GET /solutions/{id}/export.pdf y persistencia de contactos."""

import os
import uuid

import pytest

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None
MONGO_AVAILABLE = os.getenv("MONGO_URL") is not None


@pytest.mark.skipif(not (POSTGRES_AVAILABLE and MONGO_AVAILABLE), reason="PostgreSQL/MongoDB not configured")
class TestExportEndpoint:
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

    def _solve_with_contacts(self, client, token, instancia_id):
        return client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20)],
                "demands": [10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
                "contacts": [
                    {"customer_name": "Ana Torres", "customer_phone": "999111222", "address": "Av. Siempre Viva 123"},
                    None,
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_export_pdf_returns_pdf_content_type(self):
        client = self._client()
        token = self._register_owner(client, "Export Co A")
        instancia_id = f"export-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, token, instancia_id).status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF-")

    def test_export_pdf_filters_by_vehicle_id(self):
        client = self._client()
        token = self._register_owner(client, "Export Co B")
        instancia_id = f"export-vid-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, token, instancia_id).status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf?vehicle_id=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.content.count(b"/Type /Page\n") == 1

    def test_export_pdf_requires_auth(self):
        client = self._client()
        response = client.get("/solutions/anything/export.pdf")
        assert response.status_code == 401

    def test_export_pdf_404_for_other_account(self):
        client = self._client()
        token_a = self._register_owner(client, "Export Co C")
        token_b = self._register_owner(client, "Export Co D")
        instancia_id = f"export-iso-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, token_a, instancia_id).status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert response.status_code == 404

    def test_contacts_persist_and_round_trip_via_instances_list(self):
        """No hay endpoint que exponga contactos crudos — se valida indirectamente:
        el PDF no debe caer en 500 y debe reflejar el nombre dado en /solve."""
        client = self._client()
        token = self._register_owner(client, "Export Co E")
        instancia_id = f"export-contact-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, token, instancia_id).status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        # reportlab no comprime texto por defecto en A4 simple -> el nombre aparece
        # en claro dentro del content stream del PDF.
        assert b"Ana Torres" in response.content
