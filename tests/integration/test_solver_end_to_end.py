"""
Tests de integración: Orquestador Python + C++ core.
Valida que la secuencia completa funcione.
"""

import pytest
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia,
    Ruta, Solucion
)
from backend_python.service.solver_orchestrator import (
    SolverOrchestrator, solve_instance
)


@pytest.fixture
def simple_instance():
    """Instancia simple: 3 clientes, 1 vehículo."""
    depot = Deposito(Coordinate(0.0, 0.0), "Depot")
    flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=1000)
    clientes = [
        Cliente(1, Coordinate(10.0, 0.0), 100),
        Cliente(2, Coordinate(0.0, 10.0), 100),
        Cliente(3, Coordinate(10.0, 10.0), 100),
    ]
    return Instancia(
        id="test_simple",
        deposito=depot,
        flota=flota,
        clientes=clientes
    )


class TestSolverOrchestrator:
    """Tests para orquestador (Python fallback)."""

    def test_orchestrator_python_fallback(self, simple_instance):
        """Resolver con fallback Python puro (sin C++)."""
        orchestrator = SolverOrchestrator(simple_instance)
        cost_lookup = orchestrator._build_cost_lookup()
        solution = orchestrator._solve_python_fallback(cost_lookup)

        assert solution.instancia_id == "test_simple"
        assert len(solution.rutas) > 0
        assert solution.costo_total > 0

    def test_orchestrator_solve_returns_valid_solution(self, simple_instance):
        """solve() retorna Solucion válida (pasa validación)."""
        orchestrator = SolverOrchestrator(simple_instance)
        solution = orchestrator.solve()

        # Validaciones de invariantes
        assert len(solution.rutas) >= 1
        assert solution.costo_total >= 0

        # Todos los clientes visitados
        all_visited = set()
        for ruta in solution.rutas:
            all_visited.update(ruta.secuencia)

        # Debería tener los 3 clientes
        assert len(all_visited) == len(simple_instance.clientes)

    def test_solve_instance_convenience_function(self, simple_instance):
        """Función de conveniencia solve_instance() funciona."""
        solution = solve_instance(simple_instance)

        assert isinstance(solution, Solucion)
        assert solution.instancia_id == "test_simple"


class TestSolverCapacityConstraints:
    """Valida que se respeten restricciones de capacidad."""

    def test_routes_respect_vehicle_capacity(self, simple_instance):
        """Cada ruta respeta capacidad del vehículo."""
        solution = solve_instance(simple_instance)

        for ruta in solution.rutas:
            # Demanda total en ruta
            total_demand = sum(
                c.demanda
                for c in simple_instance.clientes
                if c.id in ruta.secuencia
            )

            assert total_demand <= simple_instance.flota.capacidad_por_vehiculo

    def test_infeasible_instance_raises_error(self):
        """Instancia infactible (demanda > capacidad) lanza error en creación."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=100)
        clientes = [
            Cliente(1, Coordinate(10.0, 0.0), 60),
            Cliente(2, Coordinate(0.0, 10.0), 60),  # 60 + 60 = 120 > 100
        ]

        with pytest.raises(ValueError, match="demanda total excede capacidad"):
            Instancia(
                id="test_infeasible",
                deposito=depot,
                flota=flota,
                clientes=clientes
            )


class TestSolverCostCalculation:
    """Valida que los costos se calculen correctamente."""

    def test_solution_cost_is_positive(self, simple_instance):
        """Costo de solución siempre >= 0."""
        solution = solve_instance(simple_instance)
        assert solution.costo_total >= 0

    def test_solution_cost_equals_sum_of_route_costs(self, simple_instance):
        """costo_total == sum(ruta.costo)."""
        solution = solve_instance(simple_instance)
        route_sum = sum(r.costo for r in solution.rutas)

        # Floating point tolerance
        assert abs(solution.costo_total - route_sum) < 1e-6
