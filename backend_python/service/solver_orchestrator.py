"""
Orquestador: integra C++ core con validación Python.
Ejecuta secuencia: construcción → optimización → validación.
"""

from typing import Dict, List, Tuple
import logging
import sys
import os

# Import del modelo de dominio
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia,
    Ruta, Solucion, distancia_euclidiana
)
from backend_python.config import get_config
from backend_python.service.osrm_client import get_osrm_matrix, OSRMError

# En Windows, las extensiones .pyd compiladas con MinGW no resuelven sus DLLs
# de runtime (libgcc, libstdc++, libwinpthread) vía PATH desde Python 3.8+ —
# requieren os.add_dll_directory() explícito. MINGW_BIN_DIR es opcional
# (.env.local, no versionado, específico de cada máquina); sin ella, el
# import de vrp_solver simplemente falla y el sistema usa el fallback Python.
if sys.platform == "win32":
    mingw_bin_dir = os.getenv("MINGW_BIN_DIR")
    if mingw_bin_dir and os.path.isdir(mingw_bin_dir):
        os.add_dll_directory(mingw_bin_dir)

# Importar vrp_solver (C++ bindings) - se carga en tiempo de ejecución
try:
    import vrp_solver
    HAS_CPP_BINDINGS = True
except ImportError:
    HAS_CPP_BINDINGS = False

logger = logging.getLogger(__name__)


class SolverOrchestrator:
    """Orquestador que secuencia: Construcción (NN) → Optimización (SA) → Pulido (3-opt)."""

    def __init__(self, instance: Instancia):
        self.instance = instance
        self.solution = None
        self.log = []

    def solve(self) -> Solucion:
        """
        Resolver instancia completa: NN → SA → 3-opt + validación.

        Pipeline:
        1. Construir matriz de costos (OSRM si disponible, si no euclídea)
        2. Nearest Neighbor (construcción)
        3. Simulated Annealing (optimización)
        4. 3-opt Polish (refinamiento)

        La matriz de costos se construye una sola vez, antes de decidir
        el camino de resolución (fallback Python o pipeline C++), para que
        ambos caminos usen exactamente la misma fuente de distancias.

        Retorna: Solucion válida y optimizada
        """
        cost_lookup = self._build_cost_lookup()

        if not HAS_CPP_BINDINGS:
            solution = self._solve_python_fallback(cost_lookup)
        else:
            solution = self._solve_cpp_pipeline(cost_lookup)

        if len(solution.rutas) > self.instance.flota.num_vehiculos:
            raise ValueError(
                "solución requiere más vehículos de los disponibles en la flota"
            )

        return solution

    def _build_cost_lookup(self) -> Dict[Tuple[int, int], float]:
        """
        Construye la matriz de costos como dict {(from_id, to_id): distancia}.

        Intenta OSRM primero (distancias reales sobre calles); si falla o no
        está configurado, cae silenciosamente a distancia euclídea — nunca
        bloquea la resolución de la instancia.

        IDs: 0 = depósito, 1..N = clientes (mismo esquema que el pipeline C++).
        """
        node_ids = [0] + [c.id for c in self.instance.clientes]
        coords = [
            (self.instance.deposito.coordenada.x, self.instance.deposito.coordenada.y)
        ] + [(c.coordenada.x, c.coordenada.y) for c in self.instance.clientes]

        config = get_config()
        if config.OSRM_URL:
            try:
                matrix = get_osrm_matrix(
                    coords,
                    base_url=config.OSRM_URL,
                    max_table_size=config.OSRM_MAX_TABLE_SIZE,
                    timeout_seconds=config.OSRM_TIMEOUT_SECONDS,
                )
                self.log.append("Cost matrix: OSRM (calles reales)")
                return {
                    (node_ids[i], node_ids[j]): matrix[i][j]
                    for i in range(len(node_ids))
                    for j in range(len(node_ids))
                }
            except OSRMError as e:
                logger.warning(f"OSRM unavailable, falling back to euclidean distance: {e}")
                self.log.append("Cost matrix: euclidiana (OSRM no disponible)")
        else:
            self.log.append("Cost matrix: euclidiana (OSRM_URL no configurado)")

        all_coords = [Coordinate(x, y) for x, y in coords]
        return {
            (node_ids[i], node_ids[j]): distancia_euclidiana(all_coords[i], all_coords[j])
            for i in range(len(node_ids))
            for j in range(len(node_ids))
        }

    def _solve_python_fallback(self, cost_lookup: Dict[Tuple[int, int], float]) -> Solucion:
        """
        Fallback: Nearest Neighbor puro en Python (sin C++).
        Útil para testing sin compilación.
        """
        visited = set()
        rutas = []
        vehicle_id = 0

        while len(visited) < len(self.instance.clientes):
            ruta = self._construct_route_greedy(visited, vehicle_id, cost_lookup)
            if not ruta.secuencia:
                break
            rutas.append(ruta)
            visited.update(ruta.secuencia)
            vehicle_id += 1

        if not rutas:
            raise ValueError("No feasible solution found")

        return Solucion(
            instancia_id=self.instance.id,
            rutas=rutas,
            costo_total=sum(r.costo for r in rutas)
        )

    def _construct_route_greedy(
        self, visited: set, vehicle_id: int, cost_lookup: Dict[Tuple[int, int], float]
    ) -> Ruta:
        """Construct one route greedily (Nearest Neighbor)."""
        secuencia = []
        costo = 0.0
        current_id = 0  # depot
        load = 0.0

        for _ in range(len(self.instance.clientes)):
            best_client = None
            best_dist = float('inf')

            for client in self.instance.clientes:
                if client.id not in visited:
                    new_load = load + client.demanda
                    if new_load <= self.instance.flota.capacidad_por_vehiculo:
                        dist = cost_lookup[(current_id, client.id)]
                        if dist < best_dist:
                            best_dist = dist
                            best_client = client

            if best_client is None:
                break

            secuencia.append(best_client.id)
            load += best_client.demanda
            costo += best_dist
            current_id = best_client.id
            visited.add(best_client.id)

        # Close route
        if secuencia:
            costo += cost_lookup[(current_id, 0)]  # back to depot
            return Ruta(
                vehicle_id=vehicle_id,
                secuencia=secuencia,
                costo=costo
            )

        return Ruta(vehicle_id=vehicle_id, secuencia=[], costo=0.0)

    def _solve_cpp_pipeline(self, cost_lookup: Dict[Tuple[int, int], float]) -> Solucion:
        """
        Resolver vía C++ bindings con pipeline completo: NN → SA → 3-opt.

        Pasos:
        1. Build Graph + CostMatrix (C++), llenada con cost_lookup (OSRM o euclídea)
        2. Nearest Neighbor (construcción)
        3. Simulated Annealing (optimización con SA)
        4. 3-opt Polish (refinamiento)
        5. Convert Solution → Python Solucion
        """
        n_nodes = 1 + len(self.instance.clientes)

        # 1. Build C++ graph (1 nodo depósito + N clientes; NO num_vehiculos)
        graph = vrp_solver.Graph(n_nodes)

        # Add depot (id=0)
        graph.add_node(0, self.instance.deposito.coordenada.x,
                       self.instance.deposito.coordenada.y, 0)

        # Add clients (id=1..n)
        for client in self.instance.clientes:
            graph.add_node(client.id, client.coordenada.x,
                          client.coordenada.y, int(client.demanda))

        # 2. Build cost matrix from cost_lookup (OSRM o euclídea, ya resuelto en solve())
        node_ids = [0] + [c.id for c in self.instance.clientes]
        cost_matrix = vrp_solver.CostMatrix(n_nodes)
        for i, from_id in enumerate(node_ids):
            for j, to_id in enumerate(node_ids):
                if i != j:
                    cost_matrix.set_cost(i, j, cost_lookup[(from_id, to_id)])

        # 3. Nearest Neighbor (construcción inicial)
        self.log.append("Step 1: Nearest Neighbor construction")
        nn_solver = vrp_solver.NearestNeighbor(
            graph,
            cost_matrix,
            0,  # depot id
            self.instance.flota.capacidad_por_vehiculo
        )
        nn_solution = nn_solver.solve()
        self.log.append(f"  NN cost: {nn_solution.total_cost:.2f}")

        # 4. Simulated Annealing (optimización)
        self.log.append("Step 2: Simulated Annealing optimization")
        sa_params = self._compute_sa_params()
        sa_solver = vrp_solver.SimulatedAnnealing(
            graph,
            cost_matrix,
            sa_params["T0"],
            sa_params["alpha"],
            sa_params["max_iters"]
        )
        sa_solution = sa_solver.solve(nn_solution)
        self.log.append(f"  SA cost: {sa_solution.total_cost:.2f}")
        self.log.append(f"  Improvement: {(nn_solution.total_cost - sa_solution.total_cost) / nn_solution.total_cost * 100:.2f}%")

        # 5. 3-opt Polish (refinamiento final)
        self.log.append("Step 3: 3-opt Polish")
        for route in sa_solution.routes:
            vrp_solver.ThreeOpt.improve(route, cost_matrix)
        sa_solution.calculate_total_cost()
        self.log.append(f"  3-opt cost: {sa_solution.total_cost:.2f}")

        # 6. Convert C++ Solution → Python Solucion
        # cpp_route.sequence incluye el depósito (id=0) al inicio y fin de cada
        # ruta (depot -> clientes -> depot); Ruta.secuencia es solo clientes.
        rutas = []
        for cpp_route in sa_solution.routes:
            secuencia = [node_id for node_id in cpp_route.sequence if node_id != 0]
            ruta = Ruta(
                vehicle_id=cpp_route.vehicle_id,
                secuencia=secuencia,
                costo=cpp_route.cost
            )
            rutas.append(ruta)

        return Solucion(
            instancia_id=self.instance.id,
            rutas=rutas,
            costo_total=sa_solution.total_cost
        )

    def _compute_sa_params(self) -> dict:
        """
        Compute Simulated Annealing parameters heuristically.

        Heurística (Phase 2):
        - T0 proporcional a dispersión de clientes
        - alpha inversamente proporcional a tamaño
        """
        import math

        n = len(self.instance.clientes)

        # Compute client dispersal (average distance from centroid)
        cx = sum(c.coordenada.x for c in self.instance.clientes) / n if n > 0 else 0
        cy = sum(c.coordenada.y for c in self.instance.clientes) / n if n > 0 else 0

        avg_distance = 0.0
        for client in self.instance.clientes:
            dx = client.coordenada.x - cx
            dy = client.coordenada.y - cy
            avg_distance += math.sqrt(dx * dx + dy * dy)
        avg_distance /= n if n > 0 else 1

        # Heuristic parameters
        T0 = max(10.0, avg_distance / math.log(max(2, n)))
        alpha = 0.95 if n < 100 else 0.98
        max_iters = min(1000, max(100, 50 * n))

        return {
            "T0": T0,
            "alpha": alpha,
            "max_iters": max_iters
        }


def solve_instance(instance: Instancia) -> Solucion:
    """
    Convenience function: Solver una instancia y retornar solución.

    Args:
        instance: Instancia VRP (validated)

    Returns:
        Solucion: Solución validada

    Raises:
        ValueError: Si no hay solución factible
    """
    orchestrator = SolverOrchestrator(instance)
    return orchestrator.solve()
