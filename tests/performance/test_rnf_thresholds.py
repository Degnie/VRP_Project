"""
Tests de rendimiento del pipeline C++ nativo (RNF-001, RNF-002, RNF-003).

RNF-001/002/003 eran deuda técnica declarada en ADR-006
(docs/adr/ADR-006-deuda-rendimiento-3opt.md): el cuello de botella real no
era 3-opt (hipótesis inicial descartada por perfilado), sino la construcción
de CostMatrix celda por celda desde Python, cruzando la frontera pybind11
N² veces. Resuelto con CostMatrix.set_costs_bulk (carga en un solo array
NumPy) + _build_cost_matrix_array (evita el dict intermedio de 25M+
entradas). Medido en esta máquina tras el fix (bindings C++ reales, sin
ruido de red OSRM): RNF-001 ~29ms, RNF-002 ~78ms, RNF-003 ~2.2s — los tres
dentro del umbral del SPEC.

Se saltan si los bindings C++ no están compilados/cargables en esta máquina
(mismo patrón skipif que OSRM/DB en ADR-005).
"""

import time

import pytest

from backend_python.models import Coordinate, Cliente, Deposito, Flota, Instancia
from backend_python.service.solver_orchestrator import solve_instance, HAS_CPP_BINDINGS

pytestmark = pytest.mark.skipif(
    not HAS_CPP_BINDINGS, reason="bindings C++ (vrp_solver) no disponibles en esta máquina"
)


def _build_instance(n_clientes: int) -> Instancia:
    depot = Deposito(Coordinate(0.0, 0.0), "Depot")
    demanda = 10
    capacidad_por_vehiculo = 100
    num_vehiculos = max(1, (n_clientes * demanda) // capacidad_por_vehiculo + 1)
    flota = Flota(num_vehiculos=num_vehiculos, capacidad_por_vehiculo=capacidad_por_vehiculo)
    clientes = [
        Cliente(i, Coordinate(float(i % 50), float(i // 50)), demanda)
        for i in range(1, n_clientes + 1)
    ]
    return Instancia(id=f"perf_{n_clientes}", deposito=depot, flota=flota, clientes=clientes)


def test_rnf_001_instancia_pequena(monkeypatch):
    """< 100 nodos en 10-50ms (CPU).

    spec: RNF-001
    """
    from backend_python.config import config as global_config
    monkeypatch.setattr(global_config, "OSRM_URL", "")

    instance = _build_instance(50)
    start = time.perf_counter()
    solve_instance(instance)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 50


def test_rnf_002_instancia_mediana(monkeypatch):
    """100-1000 nodos en 100-500ms (CPU).

    spec: RNF-002
    """
    from backend_python.config import config as global_config
    monkeypatch.setattr(global_config, "OSRM_URL", "")

    instance = _build_instance(500)
    start = time.perf_counter()
    solve_instance(instance)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 500


def test_rnf_003_instancia_grande(monkeypatch):
    """1000-10000 nodos en 1-5 segundos (CPU).

    spec: RNF-003
    """
    from backend_python.config import config as global_config
    monkeypatch.setattr(global_config, "OSRM_URL", "")

    instance = _build_instance(5000)
    start = time.perf_counter()
    solve_instance(instance)
    elapsed_s = time.perf_counter() - start
    assert elapsed_s < 5
