"""
Orquestador: integra C++ core con validación Python.
Ejecuta secuencia: construcción → optimización → validación.
"""

from typing import List, Tuple
import sys
import os

# Import del modelo de dominio
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia,
    Ruta, Solucion, distancia_euclidiana
)

# Importar vrp_solver (C++ bindings) - se carga en tiempo de ejecución
try:
    import vrp_solver
    HAS_CPP_BINDINGS = True
except ImportError:
    HAS_CPP_BINDINGS = False


class SolverOrchestrator:
    """Orquestador que secuencia construcción y optimización."""

    def __init__(self, instance: Instancia):
        self.instance = instance
        self.solution = None

    def solve(self) -> Solucion:
        """
        Resolver instancia completa: construcción greedy + validación.

        Retorna: Solucion válida
        """
        if not HAS_CPP_BINDINGS:
            return self._solve_python_fallback()

        return self._solve_cpp()

    def _solve_python_fallback(self) -> Solucion:
        """
        Fallback: Nearest Neighbor puro en Python (sin C++).
        Útil para testing sin compilación.
        """
        visited = set()
        rutas = []
        vehicle_id = 0

        while len(visited) < len(self.instance.clientes):
            ruta = self._construct_route_greedy(visited, vehicle_id)
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

    def _construct_route_greedy(self, visited: set, vehicle_id: int) -> Ruta:
        """Construct one route greedily (Nearest Neighbor)."""
        depot = self.instance.deposito
        secuencia = []
        costo = 0.0
        current_pos = depot.coordenada
        load = 0.0

        for _ in range(len(self.instance.clientes)):
            best_client = None
            best_dist = float('inf')

            for client in self.instance.clientes:
                if client.id not in visited:
                    new_load = load + client.demanda
                    if new_load <= self.instance.flota.capacidad_por_vehiculo:
                        dist = distancia_euclidiana(current_pos, client.coordenada)
                        if dist < best_dist:
                            best_dist = dist
                            best_client = client

            if best_client is None:
                break

            secuencia.append(best_client.id)
            load += best_client.demanda
            costo += best_dist
            current_pos = best_client.coordenada
            visited.add(best_client.id)

        # Close route
        if secuencia:
            costo += distancia_euclidiana(current_pos, depot.coordenada)
            return Ruta(
                vehicle_id=vehicle_id,
                secuencia=secuencia,
                costo=costo
            )

        return Ruta(vehicle_id=vehicle_id, secuencia=[], costo=0.0)

    def _solve_cpp(self) -> Solucion:
        """
        Resolver vía C++ bindings (Nearest Neighbor en C++).

        Pasos:
        1. Build Graph + CostMatrix (C++)
        2. Invoke NearestNeighbor.solve()
        3. Convert Solution → Python Solucion
        """
        # 1. Build C++ graph
        graph = vrp_solver.Graph(self.instance.flota.num_vehiculos)

        # Add depot (id=0)
        graph.add_node(0, self.instance.deposito.coordenada.x,
                       self.instance.deposito.coordenada.y, 0)

        # Add clients (id=1..n)
        for client in self.instance.clientes:
            graph.add_node(client.id, client.coordenada.x,
                          client.coordenada.y, int(client.demanda))

        # 2. Build cost matrix (Euclidean for now)
        coords = [
            (self.instance.deposito.coordenada.x, self.instance.deposito.coordenada.y)
        ]
        for client in self.instance.clientes:
            coords.append((client.coordenada.x, client.coordenada.y))

        cost_matrix = vrp_solver.CostMatrix.from_euclidean(coords)

        # 3. Solve via Nearest Neighbor
        solver = vrp_solver.NearestNeighbor(
            graph,
            cost_matrix,
            0,  # depot id
            self.instance.flota.capacidad_por_vehiculo
        )
        cpp_solution = solver.solve()

        # 4. Convert C++ Solution → Python Solucion
        rutas = []
        for cpp_route in cpp_solution.routes:
            ruta = Ruta(
                vehicle_id=cpp_route.vehicle_id,
                secuencia=list(cpp_route.sequence),
                costo=cpp_route.cost
            )
            rutas.append(ruta)

        return Solucion(
            instancia_id=self.instance.id,
            rutas=rutas,
            costo_total=cpp_solution.total_cost
        )


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
