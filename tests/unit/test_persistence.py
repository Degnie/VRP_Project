"""
Tests para persistencia: PostgreSQL + MongoDB.
Valida CRUD operations y transacciones.
"""

import pytest
import os
from backend_python import config as _config  # noqa: F401  (triggers .env.local load)
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia,
    Ruta, Solucion
)

# Only run if DB connections available
POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None
MONGO_AVAILABLE = os.getenv("MONGO_URL") is not None


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestPostgreSQLAdapter:
    """Tests para PostgreSQL adapter."""

    def test_save_and_load_instance(self):
        """Save instance to PostgreSQL and retrieve it."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter

        adapter = PostgreSQLAdapter()
        try:
            # Create test instance
            depot = Deposito(Coordinate(0.0, 0.0), "Test Depot")
            flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=500)
            clientes = [
                Cliente(1, Coordinate(10.0, 10.0), 100),
                Cliente(2, Coordinate(20.0, 20.0), 150),
            ]
            instance = Instancia(
                id="test_pg_001",
                deposito=depot,
                flota=flota,
                clientes=clientes
            )

            # Save
            assert adapter.save_instance(instance) == True

            # Load
            loaded = adapter.load_instance("test_pg_001")
            assert loaded is not None
            assert loaded.id == "test_pg_001"
            assert len(loaded.clientes) == 2
            assert loaded.flota.num_vehiculos == 2

        finally:
            adapter.close()

    def test_list_instances(self):
        """List all instances from PostgreSQL."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter

        adapter = PostgreSQLAdapter()
        try:
            instances = adapter.list_instances()
            assert isinstance(instances, list)
            # Should have at least test_pg_001 from previous test
        finally:
            adapter.close()

    def test_update_instance(self):
        """Update existing instance (upsert)."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter

        adapter = PostgreSQLAdapter()
        try:
            depot = Deposito(Coordinate(0.0, 0.0), "Depot")
            flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=1000)
            clientes = [Cliente(1, Coordinate(5.0, 5.0), 50)]
            instance = Instancia("test_pg_update", depot, flota, clientes)

            # First save
            adapter.save_instance(instance)

            # Update (add more clients)
            clientes.append(Cliente(2, Coordinate(15.0, 15.0), 50))
            instance2 = Instancia("test_pg_update", depot, flota, clientes)
            adapter.save_instance(instance2)

            # Verify
            loaded = adapter.load_instance("test_pg_update")
            assert len(loaded.clientes) == 2

        finally:
            adapter.close()


@pytest.mark.skipif(not MONGO_AVAILABLE, reason="MongoDB not configured")
class TestMongoDBAdapter:
    """Tests para MongoDB adapter."""

    def test_save_and_load_solution(self):
        """Save solution to MongoDB and retrieve it."""
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter

        adapter = MongoDBAdapter()
        try:
            # Create test solution
            rutas = [
                Ruta(vehicle_id=0, secuencia=[1, 2], costo=100.0),
                Ruta(vehicle_id=1, secuencia=[3, 4], costo=150.0),
            ]
            solution = Solucion(
                instancia_id="test_mongo_001",
                rutas=rutas,
                costo_total=250.0
            )

            # Save
            assert adapter.save_solution(solution, {"solver": "NN", "time": 0.5}) == True

            # Load
            loaded = adapter.load_solution("test_mongo_001")
            assert loaded is not None
            assert loaded.instancia_id == "test_mongo_001"
            assert loaded.costo_total == 250.0
            assert len(loaded.rutas) == 2

        finally:
            adapter.close()

    def test_list_solutions(self):
        """List all solutions for an instance."""
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter

        adapter = MongoDBAdapter()
        try:
            solutions = adapter.list_solutions("test_mongo_001")
            assert isinstance(solutions, list)
            # Should have at least one from previous test

        finally:
            adapter.close()

    def test_save_and_load_cost_matrix(self):
        """Save cost matrix to MongoDB and retrieve it."""
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter

        adapter = MongoDBAdapter()
        try:
            # Create fake cost matrix
            import numpy as np
            matrix = np.array([[0.0, 10.0, 20.0],
                               [10.0, 0.0, 15.0],
                               [20.0, 15.0, 0.0]], dtype=np.float64)
            data = matrix.tobytes()

            # Save
            assert adapter.save_cost_matrix("test_mongo_001", 3, data) == True

            # Load
            loaded = adapter.load_cost_matrix("test_mongo_001")
            assert loaded is not None
            n, loaded_data = loaded
            assert n == 3
            assert loaded_data == data

        finally:
            adapter.close()

    def test_multiple_solutions_same_instance(self):
        """Save multiple solutions for same instance."""
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter
        import time

        adapter = MongoDBAdapter()
        try:
            # Save solution 1
            rutas1 = [Ruta(vehicle_id=0, secuencia=[1, 2, 3], costo=100.0)]
            sol1 = Solucion("test_multi", rutas1, 100.0)
            adapter.save_solution(sol1, {"iteration": 1})

            time.sleep(0.1)  # Ensure different timestamp

            # Save solution 2 (better)
            rutas2 = [Ruta(vehicle_id=0, secuencia=[1, 3, 2], costo=90.0)]
            sol2 = Solucion("test_multi", rutas2, 90.0)
            adapter.save_solution(sol2, {"iteration": 2})

            # List all
            solutions = adapter.list_solutions("test_multi")
            assert len(solutions) >= 2

            # Load latest (should be solution 2)
            latest = adapter.load_solution("test_multi")
            assert latest.costo_total == 90.0

        finally:
            adapter.close()


@pytest.mark.skipif(
    not (POSTGRES_AVAILABLE and MONGO_AVAILABLE),
    reason="PostgreSQL and MongoDB not configured"
)
class TestFullPersistencePipeline:
    """End-to-end test: solve + persist to both DBs."""

    def test_solve_persist_retrieve(self):
        """Full pipeline: solve → save PostgreSQL + MongoDB → retrieve."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter
        from backend_python.persistence.mongodb_adapter import MongoDBAdapter
        from backend_python.service.solver_orchestrator import solve_instance

        pg_adapter = PostgreSQLAdapter()
        mongo_adapter = MongoDBAdapter()

        try:
            # Create instance
            depot = Deposito(Coordinate(0.0, 0.0), "Depot")
            flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=500)
            clientes = [
                Cliente(1, Coordinate(10.0, 10.0), 100),
                Cliente(2, Coordinate(20.0, 20.0), 100),
            ]
            instance = Instancia("e2e_test", depot, flota, clientes)

            # Persist instance (PostgreSQL)
            pg_adapter.save_instance(instance)

            # Solve
            solution = solve_instance(instance)

            # Persist solution (MongoDB)
            mongo_adapter.save_solution(solution, {"phase": "Phase 2"})

            # Retrieve instance
            retrieved_inst = pg_adapter.load_instance("e2e_test")
            assert retrieved_inst is not None
            assert retrieved_inst.id == "e2e_test"

            # Retrieve solution
            retrieved_sol = mongo_adapter.load_solution("e2e_test")
            assert retrieved_sol is not None
            assert retrieved_sol.costo_total > 0

        finally:
            pg_adapter.close()
            mongo_adapter.close()
