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

    def _register_repartidor(self, client, owner_token: str):
        email = f"repa-{uuid.uuid4().hex[:8]}@test.local"
        client.post(
            "/auth/users",
            json={"email": email, "password": "clave123", "role": "repartidor"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        login = client.post("/auth/login", json={"email": email, "password": "clave123"})
        return login.json()["access_token"]

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

    def test_export_pdf_with_quote_in_instancia_id_does_not_break_header(self):
        """Bug real (Ronda 10, ciclo nuevo, dueño): "ID de instancia" es texto
        libre sin restricciones en el formulario, pero se interpolaba crudo en
        el header Content-Disposition — una comilla embebida (ej. 'Instancia
        "Norte"') lo deja mal formado, cortando el parámetro filename a mitad
        y produciendo un nombre de archivo impredecible en el navegador."""
        client = self._client()
        token = self._register_owner(client, "Export Co Special Chars")
        instancia_id = 'raro"con-comillas'
        assert self._solve_with_contacts(client, token, instancia_id).status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF-")
        assert response.headers["content-disposition"] == 'attachment; filename="ruta_raro_con-comillas.pdf"'

    def test_safe_filename_component_strips_newlines_and_quotes(self):
        """Complemento del test anterior: un salto de línea embebido en el ID
        de instancia ni siquiera puede viajar en una URL HTTP real (rechazado
        antes de llegar al servidor) — se prueba la función de saneo
        directamente para cubrir ese caso sin depender del transporte HTTP."""
        from backend_python.api import _safe_filename_component

        assert _safe_filename_component('raro"con-salto\ny-comillas') == "raro_con-salto_y-comillas"

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

    def test_export_pdf_excludes_rescheduled_clients(self):
        """Bug real (Ronda 48, operario): reschedule_instance mueve un cliente
        a una instancia nueva y lo marca delivery_status="reprogramado" en la
        ORIGINAL, pero solution.rutas[].secuencia (Mongo) nunca se recalcula
        — sin este fix, el PDF exportado de la instancia original seguía
        listando esa parada como trabajo real, con nombre/teléfono/dirección,
        indistinguible de una parada activa. Un repartidor que solo recibe el
        PDF (no la pantalla) iría a una dirección que ya no le corresponde."""
        client = self._client()
        token = self._register_owner(client, "Export Co Reprog")
        instancia_id = f"export-reprog-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, token, instancia_id).status_code == 200

        status_res = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "no_encontrado"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_res.status_code == 200
        reschedule_res = client.post(
            f"/instances/{instancia_id}/reschedule", headers={"Authorization": f"Bearer {token}"}
        )
        assert reschedule_res.status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        # "Ana Torres" es el contacto del cliente 1, ahora reprogramado — no
        # debe aparecer en el PDF de la instancia original.
        assert b"Ana Torres" not in response.content

    def test_repartidor_without_assignment_gets_403(self):
        """Bug real: cualquier repartidor con token válido podía pedir el PDF
        de cualquier vehículo (o todos, sin vehicle_id) sin tener ninguna
        asignación en la instancia, viendo nombre/teléfono/dirección de
        clientes de rutas ajenas."""
        client = self._client()
        owner_token = self._register_owner(client, "Export Co Repa Unassigned")
        repartidor_token = self._register_repartidor(client, owner_token)
        instancia_id = f"export-repa-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, owner_token, instancia_id).status_code == 200

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {repartidor_token}"}
        )
        assert response.status_code == 403

    def test_repartidor_with_assignment_only_gets_own_route(self):
        """El repartidor asignado a vehicle_id=0 no debe poder pedir el PDF
        de otro vehicle_id pasándolo explícitamente por query param — su
        propia asignación siempre gana sobre lo pedido."""
        client = self._client()
        owner_token = self._register_owner(client, "Export Co Repa Assigned")
        repartidor_token = self._register_repartidor(client, owner_token)
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {repartidor_token}"})
        repartidor_id = me.json()["id"]
        instancia_id = f"export-repa-own-{uuid.uuid4().hex[:8]}"
        assert self._solve_with_contacts(client, owner_token, instancia_id).status_code == 200
        client.put(
            f"/instances/{instancia_id}/assignments",
            json={"assignments": {"0": repartidor_id}},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = client.get(
            f"/solutions/{instancia_id}/export.pdf?vehicle_id=1",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        assert response.content.count(b"/Type /Page\n") == 1
