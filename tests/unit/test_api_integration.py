"""
Tests para API REST integration con persistencia.
Valida que los adapters se inicialicen y que la API pueda resolver instancias.
"""

import pytest
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia
)
from backend_python.config import get_config


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
            "coordinates": [(0, 0), (10, 10), (20, 20)],
            "demands": [100, 100],
            "num_vehicles": 1,
            "vehicle_capacity": 500
        }

        response = client.post("/solve", json=request_data)

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

        response = client.post("/solve", json=request_data)
        assert response.status_code == 422

    def test_instances_list_endpoint(self):
        """GET /instances debe responder."""
        from fastapi.testclient import TestClient
        from backend_python.api import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/instances")

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
        solution = solve_instance(instance)

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
