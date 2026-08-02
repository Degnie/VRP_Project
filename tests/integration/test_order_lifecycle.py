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

    def test_get_assignments_returns_saved_assignments(self):
        """Bug real: el dueño asignaba un repartidor a una ruta, pero al
        recargar la página el selector volvía a mostrar "Sin asignar" porque
        no existía ningún GET para hidratar lo ya guardado."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle GetAssign")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        response = client.get(
            f"/instances/{instancia_id}/assignments",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"0": repartidor_id}

    def test_get_assignments_requires_dueno_or_operario(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle GetAssignRole")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.get(
            f"/instances/{instancia_id}/assignments",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 403

    def test_update_client_corrects_data_without_resolving(self):
        """Antes la única forma de corregir un error de tipeo (dirección,
        teléfono, coordenada) en un cliente ya cargado era re-resolver toda
        la instancia desde cero vía el flujo de sobreescritura, perdiendo
        los estados de entrega ya marcados ese día."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClient")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={
                "x": 15.0, "y": 15.0, "demand": 25,
                "customer_name": "Juan Corregido", "customer_phone": "999888777",
                "address": "Nueva dirección 123",
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json() == {"id": 1, "x": 15.0, "y": 15.0, "demand": 25.0}

    def test_update_client_without_demand_preserves_existing_demand(self):
        """Editar solo contacto/ubicación no debería obligar al caller a
        conocer y retransmitir la demanda actual del cliente."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientNoDemand")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)  # cliente 1 tiene demanda 10

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 15.0, "y": 15.0, "customer_name": "Solo cambio contacto"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json()["demand"] == 10.0

    def test_update_client_rejects_demand_exceeding_fleet_capacity(self):
        """Bug real: editar la demanda de un cliente escribía directo a
        Postgres sin re-validar RN-005 (demanda total <= capacidad de
        flota) — dejaba la instancia corrupta hasta que un load_instance
        posterior (export PDF, reprogramación) explotaba con 500.

        spec: RN-005
        """
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientOverFleet")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)  # flota: 1 vehiculo, capacidad 100

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 15.0, "y": 15.0, "demand": 200},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 422

        # La instancia debe seguir siendo usable (no corrupta) tras el rechazo
        pdf = client.get(f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {owner_token}"})
        assert pdf.status_code == 200

    def test_update_client_rejects_demand_exceeding_largest_vehicle(self):
        """Bug real: mismo patrón que RN-005 pero para RN-006 (ningún cliente
        puede exceder la capacidad del vehículo más grande) — sin esta
        validación, un cliente con demanda editada por encima del máximo
        vehículo cuelga el builder NearestNeighbor.

        spec: RN-006
        """
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientOverVehicle")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id, num_vehicles=2)  # capacidad 100 c/u

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 15.0, "y": 15.0, "demand": 150},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 422

    def test_update_client_without_contact_fields_preserves_existing_contact(self):
        """Bug real: editar solo la coordenada (ej. desde un formulario que
        no tenía el contacto cargado, como tras una reprogramación donde
        `contacts` queda en null en el frontend) blanqueaba en silencio
        nombre/teléfono/dirección ya persistidos — el endpoint solo
        preservaba `demand` cuando se omitía, no los campos de contacto."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientPreserveContact")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        client.post(
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
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 15.0, "y": 15.0},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200

        pdf = client.get(f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {owner_token}"})
        assert b"Ana Torres" in pdf.content

    def test_update_client_with_explicit_null_clears_contact_field(self):
        """El caller SÍ puede borrar un campo de contacto a propósito
        mandándolo como null explícito — solo omitirlo preserva lo actual."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientClearContact")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        client.post(
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
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 15.0, "y": 15.0, "customer_name": None},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200

        pdf = client.get(f"/solutions/{instancia_id}/export.pdf", headers={"Authorization": f"Bearer {owner_token}"})
        assert b"Ana Torres" not in pdf.content

    def test_update_client_rejects_already_rescheduled_client(self):
        """Bug real: se podía editar x/y/nombre de un cliente cuyo pedido
        real ya fue movido a otra instancia vía reprogramación — el registro
        editado quedaba en la instancia vieja, sin efecto práctico sobre el
        pedido que el repartidor realmente va a visitar."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientRescheduled")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        client.post(f"/instances/{instancia_id}/reschedule", headers={"Authorization": f"Bearer {owner_token}"})

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 1.0, "y": 1.0},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 409

    def test_update_client_atomic_guard_rejects_race_with_concurrent_reschedule(self):
        """Bug real (Ronda 15, ciclo nuevo, operario): update_client hacía el
        UPDATE sin guard de delivery_status en el WHERE — el endpoint
        chequeaba "no reprogramado" con un SELECT SEPARADO antes de llamarlo,
        así que si un reschedule_instance concurrente marcaba al cliente
        como reprogramado DESPUÉS de ese chequeo pero ANTES del UPDATE, la
        edición se aplicaba igual sobre un pedido que ya no pertenece a la
        instancia activa, sin ningún aviso. Se prueba el adapter directo
        (sin pasar por el chequeo previo del endpoint) para aislar que el
        guard atómico del propio UPDATE es el que realmente protege."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientRace")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        client.post(f"/instances/{instancia_id}/reschedule", headers={"Authorization": f"Bearer {owner_token}"})

        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter
        from backend_python.config import get_config
        from backend_python.api import _namespaced_id

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"}).json()
        namespaced_id = _namespaced_id(me["account_id"], instancia_id)

        adapter = PostgreSQLAdapter(get_config().DATABASE_URL)
        try:
            updated = adapter.update_client(namespaced_id, 1, 1.0, 1.0, 10, None, None, None)
        finally:
            adapter.close()
        assert updated is False

    def test_update_client_404_for_unknown_client(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClient404")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.patch(
            f"/instances/{instancia_id}/clients/999",
            json={"x": 1.0, "y": 1.0, "demand": 5},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 404

    def test_update_client_rejects_out_of_range_coordinate(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientRange")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 500.0, "y": 15.0, "demand": 10},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 422

    def test_update_client_zero_demand_gives_spanish_error(self):
        """Bug real (Ronda 19, ciclo nuevo, dueño): mismo patrón que
        VehicleTypeRequest.weight_capacity_kg (Ronda 18) — Field(gt=0) sin
        validador propio dejaba pasar el mensaje crudo de Pydantic en inglés
        ("Input should be greater than 0") si demand llegaba en 0."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientZeroDemand")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 10.0, "y": 10.0, "demand": 0},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 422
        detail = str(response.json()["detail"])
        assert "Input should be greater than" not in detail
        assert "mayor a 0" in detail

    def test_update_client_requires_dueno_or_operario(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle EditClientRole")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 1.0, "y": 1.0, "demand": 5},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 403

    def test_update_client_isolated_between_accounts(self):
        client = self._client()
        token_a = self._register_owner(client, "Lifecycle EditClientIsoA")
        token_b = self._register_owner(client, "Lifecycle EditClientIsoB")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, token_a, instancia_id)

        response = client.patch(
            f"/instances/{instancia_id}/clients/1",
            json={"x": 1.0, "y": 1.0, "demand": 5},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404

    def test_delete_instance_removes_it_from_list(self):
        """Antes no había forma de sacar una instancia de prueba/duplicada
        de la lista — quedaba visible para siempre en GET /instances."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle DeleteInstance")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        list_before = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"})
        assert instancia_id in [i["id"] for i in list_before.json()]

        response = client.delete(f"/instances/{instancia_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert response.status_code == 200

        list_after = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"})
        assert instancia_id not in [i["id"] for i in list_after.json()]

    def test_resolve_existing_does_not_resurrect_instance_deleted_mid_solve(self):
        """Bug real (Ronda 17, ciclo nuevo, dueño): POST /instances/{id}/solve
        carga la instancia, corre el solve (puede tardar segundos con
        instancias grandes), y recién después llama a save_instance — un
        upsert incondicional (INSERT ... ON CONFLICT DO UPDATE). Si un
        DELETE /instances/{id} concurrente terminaba MIENTRAS el solve
        seguía en vuelo, el save_instance final "resucitaba" la instancia
        borrada, reapareciendo en GET /instances sin ningún error en
        ninguno de los dos flujos. Se simula la carrera borrando la
        instancia DESDE DENTRO del mock de solve_instance, en el punto
        exacto donde correría si las requests estuvieran intercaladas."""
        from unittest.mock import patch

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle ResolveDeleteRace")
        instancia_id = f"lc-resolvedelete-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        import backend_python.api as api_module
        original_solve_instance = api_module.solve_instance

        def racing_solve_instance(instance):
            delete_response = client.delete(
                f"/instances/{instancia_id}", headers={"Authorization": f"Bearer {owner_token}"}
            )
            assert delete_response.status_code == 200
            return original_solve_instance(instance)

        with patch.object(api_module, "solve_instance", racing_solve_instance):
            response = client.post(
                f"/instances/{instancia_id}/solve", headers={"Authorization": f"Bearer {owner_token}"}
            )
        assert response.status_code == 404

        list_after = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"})
        assert instancia_id not in [i["id"] for i in list_after.json()]

    def test_delete_intermediate_reschedule_instance_does_not_500(self):
        """Bug real (Ronda 43, confirmación): borrar una instancia B que es
        intermedia de una cadena de reprogramación A -> B -> C (B fue creada
        al reprogramar A, y B a su vez fue reprogramada hacia C) violaba la FK
        clientes.rescheduled_to_instancia_id (sin ON DELETE, a diferencia de
        route_assignments que sí tiene CASCADE) — los clientes de A siguen
        apuntando a B. El endpoint no envolvía la excepción, así que subía
        como 500 genérico sin manejar. Fix: migración 0008 agrega ON DELETE
        SET NULL a esa FK, más un catch de defensa en profundidad que
        convierte cualquier violación de FK restante en un 409 explicativo."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Delete Intermediate")
        headers = {"Authorization": f"Bearer {owner_token}"}
        instancia_a = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_a)

        reschedule_1 = client.post(f"/instances/{instancia_a}/reschedule", headers=headers)
        assert reschedule_1.status_code == 200
        instancia_b = reschedule_1.json()["new_instancia_id"]

        reschedule_2 = client.post(f"/instances/{instancia_b}/reschedule", headers=headers)
        assert reschedule_2.status_code == 200

        delete_response = client.delete(f"/instances/{instancia_b}", headers=headers)
        assert delete_response.status_code == 200

        list_after = client.get("/instances", headers=headers).json()
        assert instancia_b not in [i["id"] for i in list_after]

    def test_delete_instance_requires_dueno_or_operario(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle DeleteInstanceRole")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.delete(f"/instances/{instancia_id}", headers={"Authorization": f"Bearer {repartidor_token}"})
        assert response.status_code == 403

    def test_delete_instance_isolated_between_accounts(self):
        client = self._client()
        token_a = self._register_owner(client, "Lifecycle DeleteInstanceIsoA")
        token_b = self._register_owner(client, "Lifecycle DeleteInstanceIsoB")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, token_a, instancia_id)

        response = client.delete(f"/instances/{instancia_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert response.status_code == 404

        list_a = client.get("/instances", headers={"Authorization": f"Bearer {token_a}"})
        assert instancia_id in [i["id"] for i in list_a.json()]

    def test_assign_rejects_vehicle_id_not_in_solution(self):
        """Bug real: route_assignments no tiene FK contra las rutas reales de
        la solución — un vehicle_id inventado (o de una instancia con menos
        vehículos) quedaba asignado igual, y el repartidor asignado jamás
        veía nada en su vista, sin ningún error visible al asignarlo."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle BadVehicleId")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-badveh-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id, num_vehicles=1)

        response = self._assign(client, owner_token, instancia_id, {"5": repartidor_id})
        assert response.status_code == 422

    def test_assign_rejects_same_repartidor_on_two_vehicles(self):
        """Bug real: get_assigned_vehicle_for_repartidor asume que un
        repartidor tiene A LO SUMO un vehicle_id por instancia (su query no
        tiene ORDER BY y hace fetchone) — sin este chequeo, asignar al mismo
        repartidor a dos vehículos dejaba una de sus dos rutas invisible en
        "Mi ruta", sin ningún error ni aviso para nadie."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle DupRepartidor")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-duprepa-{uuid.uuid4().hex[:8]}"
        # Coordenadas separadas para forzar que el solver genere 2 rutas reales.
        client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (80, 80), (10.1, 10.1), (80.1, 80.1)],
                "demands": [40, 40, 40, 40],
                "num_vehicles": 2,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = self._assign(client, owner_token, instancia_id, {"0": repartidor_id, "1": repartidor_id})
        assert response.status_code == 422

    def test_solve_fails_loudly_if_mongo_save_fails(self):
        """Bug real (Ronda 4, ciclo nuevo, operario): si mongo_adapter.save_solution
        fallaba, _solve_and_persist solo logueaba un warning y devolvía 200 —
        Postgres ya tenía la topología nueva pero Mongo se quedaba con la
        solución VIEJA, sin ningún aviso. Todo lector de Mongo (GET
        /solutions, export PDF, my-route, update_delivery_status) pasaba a
        mostrar/validar contra datos obsoletos en silencio. Ahora se propaga
        como error real en vez de tragárselo."""
        from unittest.mock import patch
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle MongoFail")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"

        with patch.object(MongoDBAdapter, "save_solution", return_value=False):
            response = self._solve_instance(client, owner_token, instancia_id)
        assert response.status_code == 503

    def test_set_assignments_rejects_user_that_is_not_repartidor(self):
        """Bug real (Ronda 2, ciclo nuevo, operario): set_assignments validaba
        que el user_id exista y sea de la misma cuenta, pero nunca que su rol
        fuera "repartidor" — un dueño/operario podía quedar asignado como
        repartidor de una ruta vía llamada directa al endpoint (la UI ya
        filtra el <select>, pero el backend no lo exigía)."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle AssignRoleGuard")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        owner_id = me.json()["id"]

        response = self._assign(client, owner_token, instancia_id, {"0": owner_id})
        assert response.status_code == 422

    def test_route_assignments_unique_constraint_rejects_duplicate_at_db_level(self):
        """El 422 de set_assignments es solo una validación de aplicación —
        sin un constraint real en la base, cualquier otro camino de
        escritura (código futuro, acceso directo) podía reintroducir el
        mismo estado inválido. UNIQUE (instancia_id, repartidor_user_id)
        lo hace imposible sin importar el código de aplicación."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter, psycopg2

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle DupRepartidorDB")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-dupdb-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id, num_vehicles=1)

        # namespaced_id real: mismo formato que _namespaced_id en api/__init__.py.
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
        account_id = me.json()["account_id"]
        namespaced_id = f"{account_id}:{instancia_id}"

        adapter = PostgreSQLAdapter()
        cursor = adapter.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO route_assignments (instancia_id, vehicle_id, repartidor_user_id) VALUES (%s, %s, %s)",
                [namespaced_id, 0, repartidor_id],
            )
            adapter.conn.commit()
            with pytest.raises(psycopg2.Error):
                cursor.execute(
                    "INSERT INTO route_assignments (instancia_id, vehicle_id, repartidor_user_id) VALUES (%s, %s, %s)",
                    [namespaced_id, 1, repartidor_id],
                )
        finally:
            adapter.conn.rollback()
            cleanup = adapter.conn.cursor()
            cleanup.execute("DELETE FROM route_assignments WHERE instancia_id = %s", [namespaced_id])
            adapter.conn.commit()
            cleanup.close()
            cursor.close()

    def test_get_delivery_statuses_returns_saved_statuses_with_notes(self):
        """Bug real: SolutionSummary (vista dueño/operario) siempre arrancaba
        cada pedido en "pendiente" sin nota, incluso si el repartidor ya lo
        había marcado "Rechazado" con una nota — no había ningún GET para
        traer el estado real tras recargar la página."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle GetStatus")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "rechazado", "note": "no tenía el monto exacto"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = client.get(
            f"/instances/{instancia_id}/delivery-statuses",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["1"]["status"] == "rechazado"
        assert body["1"]["note"] == "no tenía el monto exacto"
        assert body["2"]["status"] == "pendiente"

    def test_concurrent_status_updates_on_different_clients_all_persist(self):
        """Bug real: self.conn (psycopg2) se compartía sin lock entre threads
        del threadpool de FastAPI — 5 PUT /status casi simultáneos sobre
        clientes DISTINTOS perdían 2-3 de 5 escrituras en el backend mismo
        (todas las requests devolvían 200, pero algunos UPDATE no persistían,
        sin ninguna excepción visible). Se dispara con threads reales."""
        import threading

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Concurrent Status")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        solve_res = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)],
                "demands": [10, 10, 10, 10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert solve_res.status_code == 200

        results = []
        results_lock = threading.Lock()

        def mark_entregado(cliente_id):
            res = client.put(
                f"/instances/{instancia_id}/clients/{cliente_id}/status",
                json={"status": "entregado"},
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            with results_lock:
                results.append((cliente_id, res))

        threads = [threading.Thread(target=mark_entregado, args=(cid,)) for cid in range(1, 6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(res.status_code == 200 for _, res in results)

        statuses = client.get(
            f"/instances/{instancia_id}/delivery-statuses",
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()
        assert all(statuses[str(cid)]["status"] == "entregado" for cid in range(1, 6))

    def test_resolving_same_instance_with_fewer_clients_removes_orphans(self):
        """Bug real: re-resolver la MISMA instancia con menos clientes que la
        corrida anterior (ej. el dueño corrige el archivo y saca 2 direcciones
        erróneas) dejaba las filas viejas como basura permanente en la tabla
        clientes — el ON CONFLICT DO UPDATE del batching solo toca los ids
        presentes en el payload nuevo, nunca borra los que sobran."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Shrink")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"

        first = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)],
                "demands": [10, 10, 10, 10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert first.status_code == 200

        second = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20)],
                "demands": [10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert second.status_code == 200

        summaries = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"}).json()
        summary = next(s for s in summaries if s["id"] == instancia_id)
        assert summary["num_clients"] == 2

        statuses = client.get(
            f"/instances/{instancia_id}/delivery-statuses",
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()
        assert set(statuses.keys()) == {"1", "2"}

    def test_resolving_same_instance_preserves_delivery_status_of_kept_clients(self):
        """El fix de clientes huérfanos borra por DELETE ... NOT (id = ANY(...))
        en vez de un DELETE total + re-INSERT — confirma que un cliente que
        SIGUE presente en la nueva corrida no pierde su delivery_status ya
        marcado (ej. "entregado") solo por resolver la instancia de nuevo."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Shrink Keep Status")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        # Re-resolver con los mismos 2 clientes (cliente 1 sigue presente).
        resolve_again = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20)],
                "demands": [10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resolve_again.status_code == 200

        statuses = client.get(
            f"/instances/{instancia_id}/delivery-statuses",
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()
        assert statuses["1"]["status"] == "entregado"

    def test_rejected_solve_does_not_mutate_existing_instance(self):
        """Bug real: save_instance corría y commiteaba ANTES de que
        solve_instance() validara el payload — un /solve rechazado (ej. sin
        clientes) dejaba la instancia previa borrada/vaciada en la DB aunque
        la respuesta HTTP fuera un error, y el dueño creía que no había
        pasado nada."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reject No Mutate")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        first = self._solve_instance(client, owner_token, instancia_id)
        assert first.status_code == 200

        rejected = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [],
                "demands": [],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert rejected.status_code in (400, 422)

        # La instancia original (2 clientes) debe seguir intacta.
        summaries = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"}).json()
        summary = next(s for s in summaries if s["id"] == instancia_id)
        assert summary["num_clients"] == 2

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

    def test_rechazado_status_accepted(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Rechazado")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "rechazado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rechazado"

    def test_status_update_note_persisted_and_visible_in_my_route(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Note")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        note = "Rechazó por no tener el monto exacto, volver mañana"
        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "rechazado", "note": note},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        assert response.json()["note"] == note

        my_route = client.get(
            f"/instances/{instancia_id}/my-route",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        stop = next(s for s in my_route.json()["stops"] if s["client_id"] == 1)
        assert stop["delivery_status"] == "rechazado"
        assert stop["delivery_note"] == note

    def test_reschedule_includes_rechazado_clients(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reprog Rechazado")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        client.put(
            f"/instances/{instancia_id}/clients/2/status",
            json={"status": "rechazado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        response = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert response.json()["rescheduled_client_ids"] == [2]

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

    def test_reprogramado_rejected_via_manual_status_endpoint(self):
        """Bug real (Ronda 36, dueño): setear "reprogramado" manualmente por
        acá (en vez de vía POST /instances/{id}/reschedule) dejaba al cliente
        con delivery_status="reprogramado" pero SIN rescheduled_to_instancia_id
        — huérfano para siempre: bloqueado por el guard de 409 en cualquier
        edición futura, y excluido de get_pending_clients (así que tampoco
        volvía a ser candidato a una reprogramación real)."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reprog")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "reprogramado"},
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

    def test_repartidor_delivery_statuses_scoped_to_own_route(self):
        """Bug real (Ronda 21, ciclo nuevo, repartidor): a diferencia de
        get_my_route/update_delivery_status/export_solution_pdf,
        get_delivery_statuses no restringía al repartidor a los clientes de
        SU propia ruta — podía pedir el estado/nota de TODOS los clientes de
        la instancia, incluidas rutas ajenas (las notas suelen tener datos
        sensibles del domicilio)."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle DeliveryStatusScope")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        solve_res = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20), (30, 30), (40, 40)],
                "demands": [60, 60, 60, 60],
                "num_vehicles": 2,
                "vehicle_capacity": 130,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert solve_res.status_code == 200
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        response = client.get(
            f"/instances/{instancia_id}/delivery-statuses",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        my_route = client.get(
            f"/instances/{instancia_id}/my-route",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        ).json()
        allowed_ids = {str(stop["client_id"]) for stop in my_route["stops"]}
        assert allowed_ids != {"1", "2", "3", "4"}, "el test necesita que las 2 rutas no cubran ambas todos los clientes"
        assert set(response.json().keys()) == allowed_ids

    def test_repartidor_delivery_statuses_403_without_assignment(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle DeliveryStatusNoAssign")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.get(
            f"/instances/{instancia_id}/delivery-statuses",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 403

    def test_repartidor_get_solution_scoped_to_own_route(self):
        """Bug real (Ronda 1, ciclo nuevo, repartidor): a diferencia de
        get_my_route/update_delivery_status/export_solution_pdf/
        get_delivery_statuses, get_solution no restringía al repartidor a su
        propia ruta — devolvía sequence/cost de TODOS los vehículos de la
        instancia, incluidas rutas de otros repartidores.

        spec: RN-COV-001
        """
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle GetSolutionScope")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        solve_res = client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20), (30, 30), (40, 40)],
                "demands": [60, 60, 60, 60],
                "num_vehicles": 2,
                "vehicle_capacity": 130,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert solve_res.status_code == 200
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        response = client.get(
            f"/solutions/{instancia_id}",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["routes"]) == 1
        assert data["routes"][0]["vehicle_id"] == 0

    def test_repartidor_get_solution_404_without_assignment(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle GetSolutionNoAssign")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.get(
            f"/solutions/{instancia_id}",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        assert response.json()["routes"] == []

    def test_reschedule_reflects_client_edit_that_lands_between_snapshot_and_move(self):
        """Bug real (Ronda 17, ciclo nuevo, operario): reschedule_instance
        leía los clientes pendientes UNA vez en memoria (get_pending_clients)
        y usaba ese snapshot para armar la instancia nueva, sin volver a leer
        después de mark_clients_rescheduled — un PATCH /clients/{id} que
        editara un dato (ej. corregir la dirección) DESPUÉS de ese snapshot
        pero ANTES/DURANTE el guard atómico del reschedule se perdía en
        silencio: ambos requests devolvían 200, pero la instancia nueva
        conservaba el dato VIEJO. Se simula la carrera editando el cliente
        DESDE DENTRO del mock de mark_clients_rescheduled, en el punto
        exacto donde correría si las requests estuvieran intercaladas."""
        from unittest.mock import patch

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle RescheduleEditRace")
        instancia_id = f"lc-rescheduleeditrace-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter
        original_mark_clients_rescheduled = PostgreSQLAdapter.mark_clients_rescheduled

        def racing_mark_clients_rescheduled(self, namespaced_id_arg, cliente_ids, new_namespaced_id_arg):
            patch_response = client.patch(
                f"/instances/{instancia_id}/clients/1",
                json={"x": 10.0, "y": 10.0, "address": "Dirección corregida en la carrera"},
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert patch_response.status_code == 200
            return original_mark_clients_rescheduled(self, namespaced_id_arg, cliente_ids, new_namespaced_id_arg)

        with patch.object(PostgreSQLAdapter, "mark_clients_rescheduled", racing_mark_clients_rescheduled):
            response = client.post(
                f"/instances/{instancia_id}/reschedule",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
        assert response.status_code == 200
        new_instancia_id = response.json()["new_instancia_id"]

        # La instancia NUEVA (la que se arma con new_clientes) es donde el
        # bug se manifestaba: sin el fix, quedaba con la dirección VIEJA
        # (capturada en el snapshot get_pending_clients, antes del PATCH).
        from backend_python.config import get_config
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter as PGA
        from backend_python.api import _namespaced_id

        account_id = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"}).json()["account_id"]
        namespaced_new = _namespaced_id(account_id, new_instancia_id)

        adapter = PGA(get_config().DATABASE_URL)
        try:
            new_instance = adapter.load_instance(namespaced_new, account_id=account_id)
        finally:
            adapter.close()
        assert new_instance is not None
        edited_client = next(c for c in new_instance.clientes if c.id == 1)
        assert edited_client.address == "Dirección corregida en la carrera"

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

    def test_reschedule_then_solve_existing_instance_produces_route(self):
        """Bug real: reschedule() dejaba la instancia nueva persistida en
        Postgres con los clientes pendientes correctos, pero no existía
        ningún camino para RESOLVERLA — /solve solo aceptaba coordenadas
        armadas a mano en el body, así que un operario tendría que retipear
        cada cliente reprogramado desde cero (inviable con volumen real).
        POST /instances/{id}/solve resuelve la instancia ya guardada."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle SolveRescheduled")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        reschedule_response = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert reschedule_response.status_code == 200
        new_instancia_id = reschedule_response.json()["new_instancia_id"]

        solve_response = client.post(
            f"/instances/{new_instancia_id}/solve",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert solve_response.status_code == 200
        data = solve_response.json()
        assert data["num_routes"] >= 1
        assert data["instancia_id"] == new_instancia_id

        solution = client.get(f"/solutions/{new_instancia_id}", headers={"Authorization": f"Bearer {owner_token}"})
        assert solution.status_code == 200

    def test_reschedule_with_non_contiguous_client_ids_solves_correctly(self):
        """Bug real: el pipeline C++ (Graph.add_node) exige ids de nodo
        contiguos 0..n_nodes-1 — reschedule_instance preserva los ids
        ORIGINALES de los clientes pendientes, que quedan con huecos salvo
        que se entregue exactamente el cliente de mayor id (el caso menos
        común en la práctica). Resolver la reprogramada tiraba
        "Node ID out of bounds" (500) para cualquier otro patrón de entrega."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle GapIds")
        instancia_id = f"lc-gapids-{uuid.uuid4().hex[:8]}"
        client.post(
            "/solve",
            json={
                "instancia_id": instancia_id,
                "coordinates": [(10, 10), (20, 20), (30, 30), (40, 40), (50, 50)],
                "demands": [10, 10, 10, 10, 10],
                "num_vehicles": 1,
                "vehicle_capacity": 100,
                "depot_coordinates": (0, 0),
            },
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        # Entrega el cliente de MENOR id (no el de mayor) — deja el resto
        # (2,3,4,5) con un hueco al principio en vez del prefijo 1..k.
        client.put(
            f"/instances/{instancia_id}/clients/1/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        reschedule_response = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert reschedule_response.status_code == 200
        assert reschedule_response.json()["rescheduled_client_ids"] == [2, 3, 4, 5]
        new_instancia_id = reschedule_response.json()["new_instancia_id"]

        solve_response = client.post(
            f"/instances/{new_instancia_id}/solve",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert solve_response.status_code == 200
        assert solve_response.json()["num_routes"] >= 1

        # La secuencia devuelta debe usar los ids REALES de los clientes
        # (2,3,4,5), no los índices de nodo internos (1,2,3,4).
        solution = client.get(f"/solutions/{new_instancia_id}", headers={"Authorization": f"Bearer {owner_token}"})
        all_client_ids = {c for ruta in solution.json()["routes"] for c in ruta["sequence"]}
        assert all_client_ids == {2, 3, 4, 5}

    def test_set_assignments_rejects_write_if_instance_was_resolved_again_mid_request(self):
        """Bug real (Ronda 16, ciclo nuevo, dueño): set_assignments validaba
        vehicle_id contra la solución UNA vez, al principio del request, pero
        escribía sin volver a chequear — si un "Resolver de nuevo" concurrente
        terminaba (y por diseño invalida SIEMPRE las asignaciones existentes)
        entre esa validación y el write, este endpoint podía pisar la
        invalidación con datos ya obsoletos en silencio, dejando un
        repartidor asignado a un vehicle_id con una secuencia de paradas que
        ya no es la real. Se simula la carrera mockeando load_solution para
        que devuelva una topología distinta en la segunda lectura (la que
        pasa justo antes de escribir) — mismo efecto que un re-solve
        concurrente terminando en esa ventana, sin arriesgar un deadlock real
        de threads/locks en el test."""
        from unittest.mock import patch

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle AssignRace")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-assignrace-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        from backend_python.persistence.mongodb_adapter import MongoDBAdapter
        from backend_python.models import Ruta, Solucion

        original_load_solution = MongoDBAdapter.load_solution
        call_count = {"n": 0}

        def racing_load_solution(self, instancia_id_arg, timestamp=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return original_load_solution(self, instancia_id_arg, timestamp)
            # Segunda lectura (justo antes de escribir): simula que un
            # re-solve concurrente ya terminó con una topología distinta
            # (vehicle_id 5 en vez de 0 — ninguna asignación previa sigue siendo válida).
            return Solucion(
                instancia_id=instancia_id_arg,
                rutas=[Ruta(vehicle_id=5, secuencia=[1, 2], costo=1.0)],
                costo_total=1.0,
            )

        with patch.object(MongoDBAdapter, "load_solution", racing_load_solution):
            response = self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        assert response.status_code == 409

    def test_resolving_same_instance_invalidates_stale_assignments(self):
        """Bug real: NN/SA puede recomponer completamente qué clientes caen
        en cada vehicle_id al re-resolver la MISMA instancia (ej. tras
        corregir la coordenada de un cliente vía "Resolver de nuevo") — las
        asignaciones repartidor↔vehicle_id de la corrida anterior quedaban
        vivas apuntando al mismo vehicle_id con una secuencia de paradas
        DISTINTA, sin ningún aviso. El repartidor seguía viendo "su" ruta
        pero con clientes ajenos, pudiendo entregar pedidos equivocados."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle StaleAssign")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-staleassign-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        before = client.get(f"/instances/{instancia_id}/assignments", headers={"Authorization": f"Bearer {owner_token}"})
        assert before.json() == {"0": repartidor_id}

        resolve_response = client.post(
            f"/instances/{instancia_id}/solve",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resolve_response.status_code == 200

        after = client.get(f"/instances/{instancia_id}/assignments", headers={"Authorization": f"Bearer {owner_token}"})
        assert after.json() == {}

    def test_resolving_via_plain_solve_endpoint_also_invalidates_stale_assignments(self):
        """Mismo bug que test_resolving_same_instance_invalidates_stale_assignments,
        pero por el camino de POST /solve (plano) — el que usa el flujo de
        "sobreescribir instancia existente" del formulario principal, no
        solo /instances/{id}/solve. Ambos endpoints comparten
        _solve_and_persist, así que ambos deben invalidar por igual."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle StaleAssignPlainSolve")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-staleassign2-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)
        self._assign(client, owner_token, instancia_id, {"0": repartidor_id})

        before = client.get(f"/instances/{instancia_id}/assignments", headers={"Authorization": f"Bearer {owner_token}"})
        assert before.json() == {"0": repartidor_id}

        # Re-resuelve la MISMA instancia_id vía /solve (plano) — el camino
        # que dispara el diálogo de "sobreescribir" en la UI.
        resolve_response = self._solve_instance(client, owner_token, instancia_id)
        assert resolve_response.status_code == 200

        after = client.get(f"/instances/{instancia_id}/assignments", headers={"Authorization": f"Bearer {owner_token}"})
        assert after.json() == {}

    def test_solve_existing_instance_requires_dueno_or_operario(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle SolveRescheduledRole")
        repartidor_token, _ = self._register_repartidor(client, owner_token)
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.post(
            f"/instances/{instancia_id}/solve",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 403

    def test_solve_existing_instance_404_for_unknown_id(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle SolveRescheduled404")
        response = client.post(
            "/instances/does-not-exist/solve",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 404

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

    def test_reschedule_twice_does_not_duplicate_pending_clients(self):
        """Bug real: dos reprogramaciones de la misma instancia casi al mismo
        tiempo (dos usuarios, o un doble-click) leían el mismo set de
        pendientes ANTES de que la primera los marcara, y ambas creaban una
        instancia nueva con los mismos clientes — duplicando pedidos activos.
        Reproducido acá de forma determinística: la segunda llamada, tras la
        primera ya haber marcado todo como 'reprogramado', no debe volver a
        mover ningún cliente."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reschedule Twice")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        first = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert first.status_code == 200
        assert first.json()["rescheduled_client_ids"] == [1, 2]

        second = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert second.status_code == 400  # ya no quedan pendientes tras la primera

        # La instancia nueva creada por "first" debe tener exactamente los 2
        # clientes reprogramados — no vacía (el placeholder que se crea antes
        # de marcar) ni con clientes de más.
        new_instancia_id = first.json()["new_instancia_id"]
        summaries = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"}).json()
        new_summary = next(s for s in summaries if s["id"] == new_instancia_id)
        assert new_summary["num_clients"] == 2

    def test_solve_response_reports_used_osrm_false_when_unavailable(self, monkeypatch):
        """Bug real (Ronda 13, ciclo nuevo, dueño y operario, hallado
        independientemente por ambos): la respuesta de /solve no exponía si
        el costo/secuencia se calcularon con OSRM o con fallback euclídeo —
        el dueño veía el mismo total_cost sea cual sea el caso, sin aviso."""
        from backend_python.config import config as global_config

        monkeypatch.setattr(global_config, "OSRM_URL", "")

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle UsedOsrmFalse")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"

        response = self._solve_instance(client, owner_token, instancia_id)
        assert response.status_code == 200
        assert response.json()["used_osrm"] is False

    def test_reschedule_cleans_up_placeholder_if_postgres_fails_mid_flow(self):
        """Bug real (Ronda 3, ciclo nuevo, operario): reschedule_instance crea
        un placeholder de 0 clientes ANTES de mark_clients_rescheduled (la FK
        de rescheduled_to_instancia_id lo exige). Si Postgres falla justo
        entre esos dos pasos (corte de conexión, timeout), el placeholder
        quedaba huérfano para siempre — a diferencia del caso de "perdió la
        carrera" (moved_ids vacío), que sí lo limpiaba."""
        from unittest.mock import patch
        from backend_python.persistence.postgres_adapter import psycopg2

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reschedule DBFail")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        with patch(
            "backend_python.persistence.postgres_adapter.PostgreSQLAdapter.mark_clients_rescheduled",
            side_effect=psycopg2.Error("simulated connection loss"),
        ):
            # El TestClient re-lanza excepciones no manejadas por defecto
            # (raise_server_exceptions=True) en vez de devolver el 500 que un
            # cliente HTTP real vería — lo que importa acá es que la
            # excepción SIGUE propagándose (no se traga silenciosamente) y
            # que el placeholder se limpia antes de eso.
            with pytest.raises(psycopg2.Error):
                client.post(
                    f"/instances/{instancia_id}/reschedule",
                    headers={"Authorization": f"Bearer {owner_token}"},
                )

        # El placeholder no debe quedar visible como instancia fantasma.
        summaries = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"}).json()
        assert all(not s["id"].startswith(f"{instancia_id}-reprog-") for s in summaries)

        # La instancia original sigue teniendo sus pendientes intactos —
        # una reprogramación real (sin el mock) ahora sí debe funcionar.
        retry = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert retry.status_code == 200
        assert retry.json()["rescheduled_client_ids"] == [1, 2]

    def test_reschedule_concurrent_requests_never_duplicate_clients(self):
        """Bug real: dos reprogramaciones REALMENTE concurrentes (no
        secuenciales) sobre la misma instancia podían ambas leer el mismo set
        de pendientes antes de que ninguna marcara nada, resultando en dos
        instancias nuevas con los mismos clientes duplicados. Se dispara con
        threads reales (no requests secuenciales) para forzar la carrera."""
        import threading

        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reschedule Concurrent")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        results = []
        results_lock = threading.Lock()

        def do_reschedule():
            res = client.post(
                f"/instances/{instancia_id}/reschedule",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            with results_lock:
                results.append(res)

        threads = [threading.Thread(target=do_reschedule) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [r for r in results if r.status_code == 200]
        assert len(successes) == 1  # solo una request pudo reclamar los pendientes

        rescheduled_ids_seen = set()
        for r in successes:
            ids = r.json()["rescheduled_client_ids"]
            assert not (rescheduled_ids_seen & set(ids))  # sin solapamiento
            rescheduled_ids_seen.update(ids)

        # Ninguna instancia nueva (ganadora o "perdedora") debe tener
        # clientes de más — cada una solo con lo que realmente reclamó.
        summaries = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"}).json()
        reprog_summaries = [s for s in summaries if "-reprog-" in s["id"]]
        total_clients_across_reprog = sum(s["num_clients"] for s in reprog_summaries)
        assert total_clients_across_reprog == len(rescheduled_ids_seen)

        # Las 4 requests que perdieron la carrera (409) no deben dejar NINGUNA
        # instancia fantasma de 0 clientes visible — el placeholder que
        # reschedule_instance crea antes de marcar atómicamente se borra si
        # esta request no logra reclamar ningún cliente.
        assert len(reprog_summaries) == 1  # solo la ganadora queda persistida

    def test_cannot_update_status_of_rescheduled_client(self):
        """Bug real: un cliente ya reprogramado (movido a otra instancia)
        podía seguir marcándose "entregado" en la instancia vieja, dejando un
        registro falso mientras el pedido real seguía pendiente en la
        instancia nueva, sin ningún aviso."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle Reprog Lock")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        reschedule_res = client.post(
            f"/instances/{instancia_id}/reschedule",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert reschedule_res.status_code == 200
        rescheduled_id = reschedule_res.json()["rescheduled_client_ids"][0]

        response = client.put(
            f"/instances/{instancia_id}/clients/{rescheduled_id}/status",
            json={"status": "entregado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 409

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

    def test_assigned_only_filters_to_repartidor_routes(self):
        """Etapa D: el repartidor con assigned_only=true solo ve instancias
        donde tiene una route_assignment, no todas las de la cuenta."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle L")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)

        assigned_id = f"lc-assigned-{uuid.uuid4().hex[:8]}"
        unassigned_id = f"lc-unassigned-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, assigned_id)
        self._solve_instance(client, owner_token, unassigned_id)
        self._assign(client, owner_token, assigned_id, {"0": repartidor_id})

        response = client.get(
            "/instances", params={"assigned_only": "true"},
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        ids = [i["id"] for i in response.json()]
        assert assigned_id in ids
        assert unassigned_id not in ids

    def test_list_instances_repartidor_scoped_without_assigned_only_param(self):
        """Bug real (Ronda 1, ciclo nuevo, repartidor): el filtro a "solo mis
        instancias asignadas" dependía de que el caller pasara
        assigned_only=true — un repartidor llamando /instances directo (sin
        ese query param) veía metadata de instancias ajenas de la cuenta."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle ListInstancesNoParam")
        repartidor_token, repartidor_id = self._register_repartidor(client, owner_token)

        assigned_id = f"lc-assigned-{uuid.uuid4().hex[:8]}"
        unassigned_id = f"lc-unassigned-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, assigned_id)
        self._solve_instance(client, owner_token, unassigned_id)
        self._assign(client, owner_token, assigned_id, {"0": repartidor_id})

        response = client.get(
            "/instances",
            headers={"Authorization": f"Bearer {repartidor_token}"},
        )
        assert response.status_code == 200
        ids = [i["id"] for i in response.json()]
        assert assigned_id in ids
        assert unassigned_id not in ids

    def test_assigned_only_ignored_for_owner(self):
        """assigned_only solo aplica a repartidor — dueño sigue viendo todo."""
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle M")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.get(
            "/instances", params={"assigned_only": "true"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        assert instancia_id in [i["id"] for i in response.json()]

    def test_instance_summary_includes_created_at(self):
        client = self._client()
        owner_token = self._register_owner(client, "Lifecycle N")
        instancia_id = f"lc-{uuid.uuid4().hex[:8]}"
        self._solve_instance(client, owner_token, instancia_id)

        response = client.get("/instances", headers={"Authorization": f"Bearer {owner_token}"})
        summary = next(i for i in response.json() if i["id"] == instancia_id)
        assert summary["created_at"] is not None
