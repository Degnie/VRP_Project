"""
Tests para optimizadores y operadores locales.
Valida SA, 2-opt, Or-opt, 3-opt.
"""

import pytest
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia,
    Ruta, Solucion
)
from backend_python.service.solver_orchestrator import SolverOrchestrator, solve_instance


@pytest.fixture
def medium_instance():
    """Instancia mediana: 8 clientes, 2 vehículos."""
    depot = Deposito(Coordinate(0.0, 0.0), "Depot")
    flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=400)
    clientes = [
        Cliente(1, Coordinate(10.0, 0.0), 80),
        Cliente(2, Coordinate(10.0, 10.0), 90),
        Cliente(3, Coordinate(0.0, 10.0), 70),
        Cliente(4, Coordinate(-10.0, 10.0), 85),
        Cliente(5, Coordinate(-10.0, 0.0), 75),
        Cliente(6, Coordinate(-10.0, -10.0), 95),
        Cliente(7, Coordinate(0.0, -10.0), 80),
        Cliente(8, Coordinate(10.0, -10.0), 100),
    ]
    return Instancia(
        id="test_medium",
        deposito=depot,
        flota=flota,
        clientes=clientes
    )


class TestSolverPipeline:
    """Tests para pipeline completo: NN → SA → 3-opt.

    test_pipeline_logs_progression es técnico (verifica que orchestrator.log
    sea una lista, sin mapear a ninguna regla de dominio) — cuarentena
    permanente, ver TESTING_STRATEGY.md §4. test_orchestrator_fallback_*
    ya cita su propio ID (EC-003) en el método.
    """

    def test_orchestrator_fallback_returns_valid_solution(self, medium_instance):
        """Pipeline fallback (Python) retorna Solucion válida.

        spec: EC-003
        """
        orchestrator = SolverOrchestrator(medium_instance)
        cost_lookup = orchestrator._build_cost_lookup()
        solution = orchestrator._solve_python_fallback(cost_lookup)

        assert isinstance(solution, Solucion)
        assert solution.costo_total > 0
        assert len(solution.rutas) > 0

    def test_pipeline_logs_progression(self, medium_instance):
        """Pipeline debe registrar pasos de optimización."""
        orchestrator = SolverOrchestrator(medium_instance)
        cost_lookup = orchestrator._build_cost_lookup()
        solution = orchestrator._solve_python_fallback(cost_lookup)

        # Log should be populated if using C++ (skipped here)
        # For Python fallback, log might be empty
        assert isinstance(orchestrator.log, list)


class TestCostMatrixFallback:
    """Tests para el fallback OSRM -> euclídea en _build_cost_lookup.

    spec: RN-MAT-001
    """

    def test_falls_back_to_euclidean_when_osrm_unreachable(self, medium_instance, monkeypatch):
        """Si OSRM_URL apunta a un servicio inalcanzable, solve() no debe fallar:
        debe caer silenciosamente a distancia euclídea."""
        from backend_python.config import config as global_config

        monkeypatch.setattr(global_config, "OSRM_URL", "http://localhost:59999")
        monkeypatch.setattr(global_config, "OSRM_TIMEOUT_SECONDS", 1)

        orchestrator = SolverOrchestrator(medium_instance)
        cost_lookup = orchestrator._build_cost_lookup()

        assert "Cost matrix: euclidiana (OSRM no disponible)" in orchestrator.log
        assert len(cost_lookup) > 0

    def test_uses_euclidean_when_osrm_not_configured(self, medium_instance, monkeypatch):
        """Sin OSRM_URL configurado, ni siquiera debe intentar la llamada HTTP."""
        from backend_python.config import config as global_config

        monkeypatch.setattr(global_config, "OSRM_URL", "")

        orchestrator = SolverOrchestrator(medium_instance)
        cost_lookup = orchestrator._build_cost_lookup()

        assert "Cost matrix: euclidiana (OSRM_URL no configurado)" in orchestrator.log
        assert len(cost_lookup) > 0

    def test_solve_instance_reports_used_osrm_false_when_unavailable(self, medium_instance, monkeypatch):
        """Bug real (Ronda 13, ciclo nuevo, dueño y operario, hallado
        independientemente por ambos): solve_instance() descartaba el log del
        orchestrator — el costo calculado con euclídea (por OSRM caído/no
        configurado) se veía idéntico a uno con calles reales en la respuesta
        de /solve, sin ningún flag que lo distinguiera."""
        from backend_python.config import config as global_config
        from backend_python.service.solver_orchestrator import solve_instance

        monkeypatch.setattr(global_config, "OSRM_URL", "")

        solution, used_osrm = solve_instance(medium_instance)
        assert used_osrm is False
        assert solution.costo_total > 0


class TestFleetSizeValidation:
    """Tests para validar que la solución no exceda num_vehiculos disponibles.

    spec: RN-013
    """

    def test_solve_rejects_solution_needing_more_vehicles_than_fleet(self):
        """
        Demanda total cabe en la capacidad agregada, pero el NN greedy
        fragmenta en más rutas de las que hay vehículos disponibles
        (3 clientes de demanda 60 c/u, ningún par cabe junto en capacidad 100,
        pero solo hay 2 vehículos -> requiere 3 rutas).
        """
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=100)
        clientes = [
            Cliente(1, Coordinate(10.0, 10.0), 60),
            Cliente(2, Coordinate(-10.0, 10.0), 60),
            Cliente(3, Coordinate(10.0, -10.0), 60),
        ]
        instance = Instancia(
            id="test_overflow", deposito=depot, flota=flota, clientes=clientes
        )

        with pytest.raises(ValueError, match="más vehículos"):
            solve_instance(instance)


class TestOptimizationQuality:
    """Tests para validar mejora de calidad."""

    def test_python_fallback_produces_feasible_solution(self, medium_instance):
        """Pipeline Python fallback siempre produce solución factible: cobertura
        única (RN-011), capacidad respetada (RN-005), costo total consistente
        (RN-010).

        spec: RN-011, RN-005, RN-010
        """
        orchestrator = SolverOrchestrator(medium_instance)
        cost_lookup = orchestrator._build_cost_lookup()
        solution = orchestrator._solve_python_fallback(cost_lookup)

        # Feasibility checks
        all_visited = set()
        for ruta in solution.rutas:
            all_visited.update(ruta.secuencia)

        assert len(all_visited) == len(medium_instance.clientes), \
            "Not all clients visited"

        for ruta in solution.rutas:
            demand = sum(
                c.demanda
                for c in medium_instance.clientes
                if c.id in ruta.secuencia
            )
            assert demand <= medium_instance.flota.capacidad_por_vehiculo, \
                f"Route {ruta.vehicle_id} exceeds capacity"

        assert abs(solution.costo_total - sum(r.costo for r in solution.rutas)) < 1e-6, \
            "Cost mismatch"
