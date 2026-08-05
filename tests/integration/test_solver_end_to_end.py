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
    SolverOrchestrator, solve_instance, solve_instance_with_retries, _route_duration_hours
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
        solution, _ = solve_instance(simple_instance)

        assert isinstance(solution, Solucion)
        assert solution.instancia_id == "test_simple"


class TestSolverCapacityConstraints:
    """Valida que se respeten restricciones de capacidad."""

    def test_routes_respect_vehicle_capacity(self, simple_instance):
        """Cada ruta respeta capacidad del vehículo."""
        solution, _ = solve_instance(simple_instance)

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
        solution, _ = solve_instance(simple_instance)
        assert solution.costo_total >= 0

    def test_solution_cost_equals_sum_of_route_costs(self, simple_instance):
        """costo_total == sum(ruta.costo)."""
        solution, _ = solve_instance(simple_instance)
        route_sum = sum(r.costo for r in solution.rutas)

        # Floating point tolerance
        assert abs(solution.costo_total - route_sum) < 1e-6


class TestMaxRouteDurationOrchestration:
    """RN-026: si una ruta excede 8h (distancia/VELOCIDAD_PROMEDIO_KMH +
    15min por cliente), el orquestador debe descartar la solución, retirar
    los pedidos menos prioritarios/lejanos y reintentar con el grupo
    reducido, hasta 5 intentos.

    spec: RN-026
    """

    def test_route_over_8h_triggers_postponement_retry(self):
        """Una instancia con un solo vehículo y clientes muy dispersos
        (distancia total >> 8h de conducción a 30 km/h) obliga al
        orquestador a reintentar retirando el cliente más lejano, hasta que
        la ruta resultante quepa en 8h."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        # 1 solo vehículo con capacidad de sobra: la única razón para que la
        # ruta no quepa en 8h es la distancia, no la capacidad.
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=10000)
        # 300 km ida + 300 km vuelta a 30 km/h = 20h, muy por encima de 8h.
        clientes = [Cliente(1, Coordinate(300.0, 0.0), 10)]
        instance = Instancia(id="test_over_8h", deposito=depot, flota=flota, clientes=clientes)

        solution, _, postponed = solve_instance_with_retries(instance)

        assert all(
            _route_duration_hours(ruta, instance) <= 8.0 + 1e-6
            for ruta in solution.rutas
        )

    def test_postponed_clients_are_the_farthest(self):
        """Con 2 clientes donde solo uno cabe en 8h, el orquestador debe
        posponer el más lejano, no uno arbitrario."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=10000)
        clientes = [
            Cliente(1, Coordinate(50.0, 0.0), 10),   # cerca: cabe en 8h
            Cliente(2, Coordinate(300.0, 0.0), 10),  # lejos: no cabe
        ]
        instance = Instancia(id="test_postpone_farthest", deposito=depot, flota=flota, clientes=clientes)

        solution, _, postponed = solve_instance_with_retries(instance)

        assert 2 in postponed
        assert 1 not in postponed

    def test_max_5_retries_keeps_last_valid_solution(self):
        """Si tras 5 reintentos ninguna combinación cabe en 8h (caso
        degenerado, cliente único inevitablemente lejano), el orquestador se
        queda con la última solución obtenida en vez de ciclar para
        siempre o fallar."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=10000)
        # Un único cliente, inevitablemente >8h — no hay nada que postergar
        # (postergar el único cliente dejaría la ruta vacía), así que el
        # orquestador debe devolver esta solución tal cual sin ciclar.
        clientes = [Cliente(1, Coordinate(1000.0, 0.0), 10)]
        instance = Instancia(id="test_no_convergence", deposito=depot, flota=flota, clientes=clientes)

        solution, _, postponed = solve_instance_with_retries(instance)

        assert len(solution.rutas) == 1
        assert solution.rutas[0].secuencia == [1]
        assert postponed == []


class TestFleetSubutilizationOrchestration:
    """RN-027: si una ruta resultante toma menos de 5h, el orquestador debe
    descartar la solución, reducir en 1 el número de vehículos disponibles
    (dejándolo inactivo) y reintentar para forzar la consolidación de carga,
    hasta 5 intentos.

    spec: RN-027
    """

    def test_route_under_5h_triggers_fleet_reduction_retry(self):
        """2 vehículos con clientes muy cercanos al depósito (ruta de minutos,
        <<5h) deben consolidarse en menos vehículos si eso sigue siendo
        factible en capacidad."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=1000)
        clientes = [
            Cliente(1, Coordinate(1.0, 0.0), 10),
            Cliente(2, Coordinate(0.0, 1.0), 10),
        ]
        instance = Instancia(id="test_under_5h", deposito=depot, flota=flota, clientes=clientes)

        solution, _, _ = solve_instance_with_retries(instance)

        # Con ambos clientes cabiendo cómodos en 1 solo vehículo (capacidad
        # 1000 >> 20 de demanda total) y rutas de minutos, el orquestador
        # debe haber consolidado a 1 sola ruta en vez de dejar 2 vehículos
        # subutilizados.
        assert len(solution.rutas) == 1

    def test_fleet_reduction_does_not_go_below_1_vehicle(self):
        """Nunca reduce a 0 vehículos activos, aunque la ruta sea muy corta."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=1000)
        clientes = [Cliente(1, Coordinate(1.0, 0.0), 10)]
        instance = Instancia(id="test_single_vehicle_floor", deposito=depot, flota=flota, clientes=clientes)

        solution, _, _ = solve_instance_with_retries(instance)

        assert len(solution.rutas) == 1
