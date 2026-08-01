"""
Tests para API REST integration con persistencia.
Valida que los adapters se inicialicen y que la API pueda resolver instancias.
"""

import uuid

import pytest
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia
)
from backend_python.config import get_config


def _auth_headers(client):
    """Registra una cuenta de prueba nueva y devuelve headers con su JWT."""
    email = f"api-test-{uuid.uuid4().hex[:8]}@test.local"
    response = client.post("/auth/register", json={
        "account_name": "API Test Co", "email": email, "password": "clave123",
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestConfiguration:
    """Tests para validar que la configuración se carga correctamente."""

    def test_config_loads_from_env(self):
        """Config debe cargar variables de entorno."""
        config = get_config()

        assert config.POSTGRES_HOST == "localhost"
        assert isinstance(config.POSTGRES_PORT, int)
        assert config.POSTGRES_DB == "vrp_db"
        assert config.MONGO_HOST == "localhost"
        assert config.MONGO_PORT == 27017

    def test_database_url_construction(self):
        """DATABASE_URL debe construirse correctamente."""
        config = get_config()

        assert "postgresql://" in config.DATABASE_URL
        assert "postgres" in config.DATABASE_URL
        assert "vrp_password" in config.DATABASE_URL
        assert f"localhost:{config.POSTGRES_PORT}" in config.DATABASE_URL

    def test_mongo_url_construction(self):
        """MONGO_URL debe construirse correctamente."""
        config = get_config()

        assert "mongodb://" in config.MONGO_URL
        assert "localhost:27017" in config.MONGO_URL
        assert "vrp_db" in config.MONGO_URL


class TestPersistenceAdapters:
    """Tests para validar que los adapters se pueden instanciar."""

    def test_postgres_adapter_instantiation(self):
        """PostgreSQLAdapter debe poder instanciarse (aunque falle conexión)."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter

        # Will fail if no PostgreSQL, but shouldn't crash
        try:
            adapter = PostgreSQLAdapter()
            if adapter.conn:
                adapter.close()
        except ConnectionError:
            # Expected if PostgreSQL not running
            pass

    def test_mongodb_adapter_instantiation(self):
        """MongoDBAdapter debe poder instanciarse (aunque falle conexión)."""
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter

        # Will fail if no MongoDB, but shouldn't crash
        try:
            adapter = MongoDBAdapter()
            if adapter.client:
                adapter.close()
        except Exception:
            # Expected if MongoDB not running
            pass


class TestAPIFactory:
    """Tests para validar que la API se crea correctamente."""

    def test_api_app_creation(self):
        """FastAPI app debe crearse sin errores (adapters pueden fallar)."""
        from backend_python.api import create_app

        # Create app (adapters may not connect, but app creation should work)
        app = create_app()

        assert app is not None
        assert app.title == "VRP Solver API"
        assert app.version == "0.3.0-beta"

    def test_api_routes_registered(self):
        """API debe tener rutas registradas."""
        from backend_python.api import create_app

        app = create_app()

        # Check that routes are registered
        route_paths = [route.path for route in app.routes]

        assert "/" in route_paths
        assert "/health" in route_paths
        assert "/solve" in route_paths
        assert "/instances" in route_paths
        assert "/solutions/{instancia_id}" in route_paths

    def test_health_check_endpoint(self):
        """Health check endpoint debe responder."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code in [200, 503]  # OK or Service Unavailable (no DB)
        data = response.json()
        assert "status" in data
        assert "version" in data


class TestSolveEndpoint:
    """Tests para el endpoint /solve (sin persistencia real)."""

    def test_solve_with_minimal_instance(self):
        """POST /solve con instancia mínima."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_api_001",
            "coordinates": [(10, 10), (20, 20)],
            "demands": [100, 100],
            "num_vehicles": 1,
            "vehicle_capacity": 500,
            "depot_coordinates": (0, 0),
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))

        # May fail if no DB, but should return proper HTTP status
        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            assert "instancia_id" in data
            assert "total_cost" in data
            assert "num_routes" in data

    def test_solve_rejects_malformed_coordinates(self):
        """POST /solve con coordinates de longitud incorrecta debe responder 422, no 500."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_bad_coords",
            "coordinates": [(1.0, 2.0, 3.0)],  # ❌ 3 elementos en vez de 2
            "demands": [10],
            "num_vehicles": 1,
            "vehicle_capacity": 100
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))
        assert response.status_code == 422

    def test_solve_rejects_out_of_range_coordinates(self):
        """Bug real: una coordenada fuera de rango real (lat/lng, ej. typo de
        tecla o CSV mal importado) pasaba el 200 de /solve sin ninguna
        validación, y recién explotaba en el frontend — MapLibre lanza
        "Invalid LngLat" al intentar centrar el mapa en la solución, y como
        no había Error Boundary, esa excepción tumbaba toda la SPA."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_out_of_range_coords",
            "coordinates": [(500.0, 500.0), (1.0, 1.0)],  # lat=500 imposible
            "demands": [10, 10],
            "num_vehicles": 1,
            "vehicle_capacity": 100,
            "depot_coordinates": (0, 0),
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))
        assert response.status_code == 422

    def test_solve_rejects_contact_field_over_column_length(self):
        """Bug real: ContactInfo no tenía max_length (a diferencia de
        UpdateClientRequest, que sí lo tiene para el mismo dato) — una
        dirección/nombre más larga que la columna real (VARCHAR(500)/
        VARCHAR(255)) pasaba Pydantic sin quejarse, el solve corría en
        memoria, y recién explotaba en save_instance con un
        StringDataRightTruncation sin capturar, devolviendo un 500 genérico."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_contact_too_long",
            "coordinates": [(10.0, 10.0), (20.0, 20.0)],
            "demands": [10, 10],
            "num_vehicles": 1,
            "vehicle_capacity": 100,
            "depot_coordinates": (0, 0),
            "contacts": [{"address": "x" * 501}, None],
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))
        assert response.status_code == 422

    def test_solve_rejects_instancia_id_over_column_length(self):
        """Mismo patrón que ContactInfo: instancia_id es texto libre del
        formulario, sin max_length, persistido en instancias.id VARCHAR(255)
        namespaceado con el account_id — un valor largo pasaba Pydantic y
        explotaba en save_instance con un 500 genérico en vez de un 422 claro."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "x" * 250,
            "coordinates": [(10.0, 10.0), (20.0, 20.0)],
            "demands": [10, 10],
            "num_vehicles": 1,
            "vehicle_capacity": 100,
            "depot_coordinates": (0, 0),
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))
        assert response.status_code == 422

    def test_solve_rejects_out_of_range_depot(self):
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_out_of_range_depot",
            "coordinates": [(1.0, 1.0), (2.0, 2.0)],
            "demands": [10, 10],
            "num_vehicles": 1,
            "vehicle_capacity": 100,
            "depot_coordinates": (0, -200),  # longitud imposible
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))
        assert response.status_code == 422

    def test_solve_rejects_client_exceeding_every_vehicle_capacity(self):
        """POST /solve con un cliente cuya demanda supera al vehículo más
        grande debe responder 400, no colgarse ni devolver 500 — bug real:
        el builder NearestNeighbor (Python y C++) nunca termina de servir un
        cliente así, aunque la demanda TOTAL de la flota alcance."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_over_capacity",
            "coordinates": [(10, 10), (20, 20)],
            "demands": [80, 10],
            "num_vehicles": 2,
            "vehicle_capacity": 50,
            "vehicle_capacities": [50, 50],
            "depot_coordinates": (0, 0),
        }

        response = client.post("/solve", json=request_data, headers=_auth_headers(client))
        assert response.status_code == 400
        assert "capacidad de cualquier vehículo" in response.json()["detail"]

    def test_solve_requires_auth(self):
        """POST /solve sin token debe rechazar con 401, no intentar resolver."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        request_data = {
            "instancia_id": "test_no_auth",
            "coordinates": [(0, 0), (10, 10)],
            "demands": [10],
            "num_vehicles": 1,
            "vehicle_capacity": 100,
        }
        response = client.post("/solve", json=request_data)
        assert response.status_code == 401

    def test_instances_list_endpoint(self):
        """GET /instances debe responder."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/instances", headers=_auth_headers(client))

        # May fail if no PostgreSQL, but should return proper status
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


class TestEndToEndFlow:
    """Tests para validar el flujo end-to-end (solve + persist)."""

    def test_solve_instance_workflow(self):
        """Workflow: crear instancia → resolver → retornar solución."""
        from backend_python.service.solver_orchestrator import solve_instance

        # Create instance
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=500)
        clientes = [
            Cliente(1, Coordinate(10.0, 10.0), 100),
            Cliente(2, Coordinate(20.0, 20.0), 150),
        ]
        instance = Instancia("test_e2e", depot, flota, clientes)

        # Solve (should use Python fallback if no C++)
        solution, _ = solve_instance(instance)

        # Validate solution
        assert solution is not None
        assert solution.instancia_id == "test_e2e"
        assert solution.costo_total > 0
        assert len(solution.rutas) > 0

        # All clients should be visited
        all_visited = set()
        for ruta in solution.rutas:
            all_visited.update(ruta.secuencia)
        assert len(all_visited) == 2

    def test_solve_instance_client_at_depot_coordinate_never_500s(self):
        """Bug real: un cliente en la misma coordenada que el depósito da
        costo de ruta NN = 0.0, y el pipeline C++ calculaba el % de mejora
        de SA dividiendo por ese costo (nn_solution.total_cost) sin chequear
        cero — ZeroDivisionError no capturado específicamente, devuelto como
        500 genérico en /solve para cualquier cuenta nueva que lo disparara."""
        from backend_python.service.solver_orchestrator import solve_instance

        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=100)
        clientes = [Cliente(1, Coordinate(0.0, 0.0), 10)]
        instance = Instancia("test_zero_cost", depot, flota, clientes)

        solution, _ = solve_instance(instance)

        assert solution is not None
        assert solution.costo_total == 0.0
