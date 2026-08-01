"""
Tests de rendimiento del pipeline C++ nativo (RNF-001, RNF-002, RNF-003).

RNF-001/002/003 son deuda técnica declarada en ADR-006
(docs/adr/ADR-006-deuda-rendimiento-3opt.md): el operador 3-opt no tiene
límite de tiempo/escala, y el costo por movimiento crece con n sin cota.
Medido en esta máquina (bindings C++ reales, sin ruido de red OSRM):
RNF-001 ~50ms (al límite), RNF-002 ~1054ms (~2x el umbral de 500ms),
RNF-003 ~443s (~90x el umbral de 5s).

No se assertan los umbrales del SPEC como passing/failing — mentiría sobre
un contrato que hoy no se cumple. Cada test solo confirma que el solver
resuelve la instancia sin fallar a esa escala; la regla de rendimiento
vigente queda anotada `spec: PENDIENTE` hasta que el ADR-006 se resuelva
con un fix real (time_limit_ms en los operadores C++).

Se saltan si los bindings C++ no están compilados/cargables en esta máquina
(mismo patrón skipif que OSRM/DB en ADR-005).
"""

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
    """< 100 nodos, objetivo 10-50ms (CPU). Deuda técnica, ver ADR-006.

    spec: PENDIENTE (RNF-001)
    """
    from backend_python.config import config as global_config
    monkeypatch.setattr(global_config, "OSRM_URL", "")

    instance = _build_instance(50)
    solution, _ = solve_instance(instance)
    assert solution.costo_total > 0


def test_rnf_002_instancia_mediana(monkeypatch):
    """100-1000 nodos, objetivo 100-500ms (CPU). Deuda técnica, ver ADR-006.

    spec: PENDIENTE (RNF-002)
    """
    from backend_python.config import config as global_config
    monkeypatch.setattr(global_config, "OSRM_URL", "")

    instance = _build_instance(500)
    solution, _ = solve_instance(instance)
    assert solution.costo_total > 0


def test_rnf_003_instancia_grande(monkeypatch):
    """1000-10000 nodos, objetivo 1-5s (CPU). Deuda técnica, ver ADR-006.

    spec: PENDIENTE (RNF-003)
    """
    from backend_python.config import config as global_config
    monkeypatch.setattr(global_config, "OSRM_URL", "")

    instance = _build_instance(5000)
    solution, _ = solve_instance(instance)
    assert solution.costo_total > 0
