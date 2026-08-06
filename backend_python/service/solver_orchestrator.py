"""
Orquestador: integra C++ core con validación Python.
Ejecuta secuencia: construcción → optimización → validación.
"""

from typing import Dict, List, Optional, Tuple
import logging
import math
import sys
import os

import numpy as np

# Import del modelo de dominio
from backend_python.models import (
    Cliente, Deposito, Flota, Instancia, Ruta, Solucion, distancia_euclidiana
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

        La matriz de costos se construye una sola vez (como array denso),
        antes de decidir el camino de resolución (fallback Python o pipeline
        C++), para que ambos caminos usen exactamente la misma fuente de
        distancias. El fallback Python necesita un dict indexado por id real
        (deriva del mismo array, sin recalcular OSRM/euclídea); el pipeline
        C++ usa el array directo (ver ADR-006).

        Retorna: Solucion válida y optimizada
        """
        node_ids, cost_array = self._build_cost_matrix_array()

        if not HAS_CPP_BINDINGS:
            cost_lookup = {
                (node_ids[i], node_ids[j]): float(cost_array[i, j])
                for i in range(len(node_ids))
                for j in range(len(node_ids))
            }
            solution = self._solve_python_fallback(cost_lookup)
        else:
            solution = self._solve_cpp_pipeline(cost_array)

        if len(solution.rutas) > self.instance.flota.num_vehiculos:
            raise ValueError(
                "solución requiere más vehículos de los disponibles en la flota"
            )

        return solution

    def _capacity_for_vehicle(self, vehicle_id: int) -> float:
        """
        Capacidad efectiva del vehículo vehicle_id (0-indexado).

        Si la flota tiene capacidades_vehiculos (heterogénea), usa
        capacities[vehicle_id % len(capacities)] — el módulo evita out-of-range
        si se construyen más rutas que capacidades explícitas (no debería
        pasar en uso normal, ya que num_vehiculos == len(capacidades)).
        Si no, usa la capacidad escalar homogénea de siempre.
        """
        capacidades = self.instance.flota.capacidades_vehiculos
        if capacidades:
            return capacidades[vehicle_id % len(capacidades)]
        return self.instance.flota.capacidad_por_vehiculo

    def _build_cost_lookup(self) -> Dict[Tuple[int, int], float]:
        """
        Construye la matriz de costos como dict {(from_id, to_id): distancia}.

        Usado por el fallback Python (_solve_python_fallback), que indexa por
        id real de cliente. El pipeline C++ usa _build_cost_matrix_array en
        su lugar (mismo cálculo, sin pasar por dict) — ver ADR-006.
        """
        node_ids, matrix = self._build_cost_matrix_array()
        return {
            (node_ids[i], node_ids[j]): float(matrix[i, j])
            for i in range(len(node_ids))
            for j in range(len(node_ids))
        }

    def _build_cost_matrix_array(self) -> Tuple[List[int], "np.ndarray"]:
        """
        Construye la matriz de costos como array NumPy 2D denso, indexado por
        posición (mismo orden que node_ids: 0 = depósito, luego clientes en
        orden de instance.clientes).

        Intenta OSRM primero (distancias reales sobre calles); si falla o no
        está configurado, cae silenciosamente a distancia euclídea — nunca
        bloquea la resolución de la instancia.

        ADR-006: fuente única para _build_cost_lookup (dict, fallback Python)
        y _solve_cpp_pipeline (array, pipeline C++) — evita reconstruir la
        matriz dos veces o pasar por un dict intermedio de 25M+ entradas en
        instancias grandes.
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
                return node_ids, np.asarray(matrix, dtype=np.float64)
            except OSRMError as e:
                logger.warning(f"OSRM unavailable, falling back to euclidean distance: {e}")
                self.log.append("Cost matrix: euclidiana (OSRM no disponible)")
        else:
            self.log.append("Cost matrix: euclidiana (OSRM_URL no configurado)")

        xs = np.array([c[0] for c in coords], dtype=np.float64)
        ys = np.array([c[1] for c in coords], dtype=np.float64)
        dx = xs[:, None] - xs[None, :]
        dy = ys[:, None] - ys[None, :]
        matrix = np.sqrt(dx * dx + dy * dy)
        return node_ids, matrix

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
        capacity = self._capacity_for_vehicle(vehicle_id)

        for _ in range(len(self.instance.clientes)):
            best_client = None
            best_dist = float('inf')

            for client in self.instance.clientes:
                if client.id not in visited:
                    new_load = load + client.demanda
                    if new_load <= capacity:
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

    def _solve_cpp_pipeline(self, cost_array: "np.ndarray") -> Solucion:
        """
        Resolver vía C++ bindings con pipeline completo: NN → SA → 3-opt.

        Pasos:
        1. Build Graph + CostMatrix (C++), llenada con cost_array (OSRM o euclídea)
        2. Nearest Neighbor (construcción)
        3. Simulated Annealing (optimización con SA)
        4. 3-opt Polish (refinamiento)
        5. Convert Solution → Python Solucion
        """
        n_nodes = 1 + len(self.instance.clientes)

        # Graph.add_node exige ids contiguos 0..n_nodes-1 (valida rango en
        # C++) — client.id es el id REAL del cliente (ej. en una instancia
        # reprogramada, son los ids originales de los pendientes, con huecos
        # si el cliente entregado no fue el de mayor id). Sin este mapeo a
        # índices contiguos, reprogramar y re-resolver tiraba
        # "Node ID out of bounds" en cualquier caso donde el subconjunto de
        # pendientes no fuera exactamente el prefijo 1..k.
        real_to_node = {client.id: i + 1 for i, client in enumerate(self.instance.clientes)}
        node_to_real = {node_id: real_id for real_id, node_id in real_to_node.items()}

        # 1. Build C++ graph (1 nodo depósito + N clientes; NO num_vehiculos)
        graph = vrp_solver.Graph(n_nodes)

        # Add depot (id=0)
        graph.add_node(0, self.instance.deposito.coordenada.x,
                       self.instance.deposito.coordenada.y, 0)

        # Add clients (id=1..n, mapeado a índice contiguo)
        for client in self.instance.clientes:
            graph.add_node(real_to_node[client.id], client.coordenada.x,
                          client.coordenada.y, int(client.demanda))

        # 2. Build cost matrix desde cost_array (OSRM o euclídea, ya resuelto
        # en solve() vía _build_cost_matrix_array) — mismo orden [depósito,
        # clientes...] que real_to_node, así que ya está indexado por índice
        # de nodo contiguo, sin conversión adicional.
        #
        # ADR-006: llenar celda por celda vía N² llamadas a set_cost cruzaba
        # la frontera pybind11 esa misma cantidad de veces — 98.4% del tiempo
        # total del pipeline en una instancia de 5,000 clientes (~84s de
        # ~85s medidos), sin que 3-opt ni SimulatedAnnealing fueran la causa.
        # set_costs_bulk recibe la matriz completa como un solo array NumPy
        # (una sola travesía de la frontera); cost_array ya viene armado como
        # array denso desde _build_cost_matrix_array, sin dict intermedio.
        cost_matrix = vrp_solver.CostMatrix(n_nodes)
        cost_matrix.set_costs_bulk(cost_array)

        # 3. Nearest Neighbor (construcción inicial)
        self.log.append("Step 1: Nearest Neighbor construction")
        capacidades = self.instance.flota.capacidades_vehiculos or (
            [self.instance.flota.capacidad_por_vehiculo] * self.instance.flota.num_vehiculos
        )
        nn_solver = vrp_solver.NearestNeighbor(
            graph,
            cost_matrix,
            0,  # depot id
            capacidades
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
        if nn_solution.total_cost > 0:
            improvement_pct = (nn_solution.total_cost - sa_solution.total_cost) / nn_solution.total_cost * 100
            self.log.append(f"  Improvement: {improvement_pct:.2f}%")

        # 5. 3-opt Polish (refinamiento final)
        self.log.append("Step 3: 3-opt Polish")
        for route in sa_solution.routes:
            vrp_solver.ThreeOpt.improve(route, cost_matrix)
        sa_solution.calculate_total_cost()
        self.log.append(f"  3-opt cost: {sa_solution.total_cost:.2f}")

        # 6. Convert C++ Solution → Python Solucion
        # cpp_route.sequence incluye el depósito (id=0) al inicio y fin de cada
        # ruta (depot -> clientes -> depot); Ruta.secuencia es solo clientes.
        # Se traduce cada índice de nodo contiguo de vuelta al id REAL del
        # cliente — Ruta.secuencia/get_pending_clients/etc. siguen operando
        # con los ids reales que el resto del sistema conoce.
        rutas = []
        for cpp_route in sa_solution.routes:
            secuencia = [node_to_real[node_id] for node_id in cpp_route.sequence if node_id != 0]
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


def _route_duration_hours(ruta: Ruta, instance: Instancia, used_osrm: bool = False) -> float:
    """Duración estimada de una ruta: tiempo de conducción
    (Ruta.costo / VELOCIDAD_PROMEDIO_KMH) + tiempo de espera fijo por
    cliente (TIEMPO_ESPERA_POR_CLIENTE_MIN).

    RN-026/RN-027. Bug real: get_osrm_matrix (osrm_client.py) entrega
    metros crudos del /table de OSRM sin ninguna conversión — dividir esos
    metros directo por una velocidad en km/h daba duraciones ~1000x más
    grandes que la realidad, disparando el postergado/reducción de flota
    aunque la ruta real durara minutos (visible con 100 pedidos y 2
    camiones: una ruta terminaba "durando" 3 días). El fallback euclídeo
    (sin OSRM, used_osrm=False) no tiene esa conversión: las coordenadas de
    test están calibradas por convención como si ya estuvieran en km.
    """
    config = get_config()
    costo_km = ruta.costo / 1000.0 if used_osrm else ruta.costo
    horas_conduccion = costo_km / config.VELOCIDAD_PROMEDIO_KMH
    horas_espera = len(ruta.secuencia) * config.TIEMPO_ESPERA_POR_CLIENTE_MIN / 60.0
    return horas_conduccion + horas_espera


def _clients_to_postpone_for_8h(ruta: Ruta, instance: Instancia, used_osrm: bool) -> List[int]:
    """Clientes de `ruta` a postergar en UN solo intento para que la
    duración estimada quepa en 8h (RN-026).

    Bug real: postergar de a 1 cliente por vuelta del bucle de reintentos
    (llamando a solve_instance completo en cada vuelta) requiere tantas
    vueltas como clientes sobran — con instancias grandes (100+ clientes,
    flota chica) esto agota MAX_REINTENTOS_ORQUESTACION mucho antes de
    converger, dejando pasar rutas de decenas de horas sin ningún aviso.
    Acá se decide de una vez, dentro del mismo intento, cuántos y cuáles
    clientes postergar (los más lejanos al depósito primero). La
    conducción restante se re-estima cada vez que se saca un cliente,
    descontando la PROPORCIÓN de su distancia euclídea al depósito sobre
    la suma total de distancias euclídeas de la ruta — una razón
    adimensional, no una resta de valores absolutos en unidades distintas.

    Bug real (versión anterior de este fix): restar "2x distancia euclídea"
    directo del costo real de la ruta mezclaba unidades — con OSRM activo
    ruta.costo son metros de calle real, pero distancia_euclidiana opera
    sobre las coordenadas crudas (grados de longitud/latitud con datos
    geográficos reales, no kilómetros). La resta apenas movía el costo
    restante y el bucle terminaba postergando casi toda la ruta (99 de 100
    clientes en una prueba real con Lima). Usar una proporción evita
    depender de que ambas cantidades compartan unidad.

    Sigue siendo una aproximación (no el recálculo real de ruta, eso
    requeriría volver a llamar al solver) pero más ajustada que prorratear
    por cantidad de paradas cuando la distribución de distancias es
    desigual. El bucle externo vuelve a resolver con el solver tras cada
    tanda, así que una sub/sobre-estimación puntual se corrige en la
    vuelta siguiente.
    """
    # Ruta de 1 solo cliente que ya excede 8h: postergarlo la vaciaría —
    # caso degenerado e irresoluble por esta vía, no hay nada que sacar.
    if len(ruta.secuencia) <= 1:
        return []

    config = get_config()
    depot = instance.deposito.coordenada
    clientes_por_id = {c.id: c for c in instance.clientes}
    costo_km_restante = ruta.costo / 1000.0 if used_osrm else ruta.costo

    distancias_euclid = {
        cid: distancia_euclidiana(depot, clientes_por_id[cid].coordenada) for cid in ruta.secuencia
    }
    suma_euclid_restante = sum(distancias_euclid.values())
    restantes = sorted(ruta.secuencia, key=lambda cid: distancias_euclid[cid])

    a_postergar: List[int] = []
    while len(restantes) > 1:
        horas_conduccion = costo_km_restante / config.VELOCIDAD_PROMEDIO_KMH
        horas_espera = len(restantes) * config.TIEMPO_ESPERA_POR_CLIENTE_MIN / 60.0
        if horas_conduccion + horas_espera <= 8.0:
            break
        # El más lejano queda al final de `restantes` (orden ascendente).
        client_id = restantes.pop()
        if suma_euclid_restante > 0:
            proporcion = distancias_euclid[client_id] / suma_euclid_restante
            costo_km_restante = max(0.0, costo_km_restante * (1 - proporcion))
        suma_euclid_restante -= distancias_euclid[client_id]
        a_postergar.append(client_id)
    return a_postergar


def _reduce_vehicle_capacity_for_8h(
    flota: Flota, over_8h: List[Ruta], durations: Dict[int, float], num_rutas_usadas: int
) -> Flota:
    """Reduce la capacidad efectiva de los vehículos sobre 8h Y de los
    vehículos TODAVÍA sin ruta que comparten esa misma capacidad grande,
    proporcional al exceso de horas — para forzar al solver a cortar esa
    ruta antes y repartir hacia varios vehículos ociosos de una sola vez,
    no de a uno por vuelta.

    RN-026 (fix de fondo): el solver base (CVRP puro, sin noción de tiempo
    — ver SPEC "Fuera de Alcance") arma rutas por distancia+peso, sin mirar
    cuántos vehículos quedan disponibles. Con una flota grande (ej. 15
    vehículos: 7 camiones de 1500kg + 8 motos de 30kg) y demanda total que
    cabe en un solo camión, el greedy metía los 172 clientes en 1 sola
    ruta de 65h y dejaba 14 vehículos sin ningún cliente asignado — la
    versión anterior de este fix posteraba 147 clientes "al día siguiente"
    en vez de usar la flota ociosa que sí estaba disponible hoy.

    Bug real de una versión intermedia: reducir solo el vehículo que ya
    excedía 8h en ESA vuelta liberaba 1 vehículo nuevo por vuelta del
    bucle (mismo patrón "de a 1" ya visto en la postergación) — con 7
    camiones de 1500kg, se necesitaban ~7 vueltas solo para tocar cada
    uno, agotando MAX_REINTENTOS_ORQUESTACION antes de converger. Ahora
    también se reduce, en la misma pasada, a todo vehículo sin ruta
    todavía cuya capacidad iguale o supere la del que sí excedió — así la
    primera reducción ya "achica" a todos los camiones grandes de una vez.
    """
    capacidades = list(
        flota.capacidades_vehiculos or ([flota.capacidad_por_vehiculo] * flota.num_vehiculos)
    )
    vehicle_ids_over = {r.vehicle_id for r in over_8h}
    for ruta in over_8h:
        factor = max(0.05, 8.0 / durations[ruta.vehicle_id])
        idx_origen = ruta.vehicle_id % len(capacidades)
        capacidad_origen = capacidades[idx_origen]
        capacidades[idx_origen] = max(1.0, capacidad_origen * factor)
        for idx in range(len(capacidades)):
            # Vehículos ya usados en esta solución (con ruta propia,
            # aunque no haya excedido 8h) no se tocan — solo los que
            # todavía no tienen ninguna ruta asignada, comparando contra
            # la capacidad ORIGINAL (antes de esta reducción) del que sí
            # excedió, para no encadenar reducciones sobre reducciones ya
            # aplicadas en esta misma pasada.
            if idx >= num_rutas_usadas and idx not in vehicle_ids_over:
                if capacidades[idx] >= capacidad_origen:
                    capacidades[idx] = max(1.0, capacidades[idx] * factor)
    return Flota(
        num_vehiculos=flota.num_vehiculos,
        capacidad_por_vehiculo=capacidades[0],
        capacidades_vehiculos=capacidades,
    )


def solve_instance_with_retries(instance: Instancia) -> Tuple[Solucion, bool, List[int]]:
    """Resuelve una instancia aplicando la orquestación VRPTW de RN-026/
    RN-027: si alguna ruta excede 8h y hay vehículos de la flota sin
    ninguna ruta asignada, se reduce la capacidad efectiva del vehículo
    sobrecargado para forzar que el solver reparta hacia esos vehículos
    ociosos en el siguiente intento. Solo se posterga clientes (fuera de
    la instancia, "al día siguiente") cuando la flota entera ya está en
    uso y aun así sobra. Si alguna ruta toma menos de 5h con flota de
    sobra, se reduce el número de vehículos y se reintenta. Máximo
    MAX_REINTENTOS_ORQUESTACION intentos — si no converge, se queda con la
    última solución obtenida en vez de ciclar indefinidamente.

    Retorna: (Solucion, used_osrm, postponed_client_ids)
    """
    config = get_config()
    current_instance = instance
    postponed: List[int] = []
    solution: Optional[Solucion] = None
    used_osrm = False

    for _ in range(config.MAX_REINTENTOS_ORQUESTACION):
        try:
            solution, used_osrm = solve_instance(current_instance)
        except ValueError:
            # RN-013: una reducción de capacidad de la vuelta anterior fue
            # demasiado agresiva y fragmentó la ruta en más subrutas de las
            # que hay vehículos disponibles — la excepción no es un error
            # real del pedido del usuario, es un efecto secundario de esta
            # orquestación heurística. Se descarta ese intento y se queda
            # con la última solución válida en vez de propagar un 500.
            if solution is None:
                raise
            break
        durations = {
            ruta.vehicle_id: _route_duration_hours(ruta, current_instance, used_osrm)
            for ruta in solution.rutas
        }

        over_8h = [r for r in solution.rutas if durations[r.vehicle_id] > 8.0]
        if over_8h:
            vehiculos_sin_ruta = current_instance.flota.num_vehiculos - len(solution.rutas)
            if vehiculos_sin_ruta > 0:
                # Hay flota ociosa: forzar reparto hacia ella reduciendo la
                # capacidad efectiva del/los vehículo(s) sobrecargados, sin
                # tocar la lista de clientes de la instancia.
                nueva_flota = _reduce_vehicle_capacity_for_8h(
                    current_instance.flota, over_8h, durations, len(solution.rutas)
                )
                try:
                    current_instance = Instancia(
                        id=current_instance.id,
                        deposito=current_instance.deposito,
                        flota=nueva_flota,
                        clientes=current_instance.clientes,
                        created_at=current_instance.created_at,
                    )
                except ValueError:
                    # Reducir capacidad para forzar el reparto dejó la
                    # flota sin espacio total para la demanda (RN-005) —
                    # la reducción fue demasiado agresiva en esta pasada;
                    # cae al camino de postergar en vez de perder la
                    # solución actual entera.
                    pass
                else:
                    continue

            # Toda la flota ya está en uso y aun así sobra: recién acá
            # postergar tiene sentido (no hay más vehículos hoy).
            # Postergar TODOS los clientes que sobran de TODAS las rutas
            # que exceden 8h en este mismo intento (no solo 1 cliente de 1
            # ruta) — con instancias grandes, postergar de a 1 por vuelta
            # agotaba MAX_REINTENTOS_ORQUESTACION mucho antes de bajar lo
            # suficiente, dejando pasar rutas de decenas de horas sin
            # converger ni avisar (ver _clients_to_postpone_for_8h).
            client_ids_a_postergar: set = set()
            for ruta in over_8h:
                client_ids_a_postergar.update(
                    _clients_to_postpone_for_8h(ruta, current_instance, used_osrm)
                )
            if not client_ids_a_postergar:
                # Ninguna ruta sobre 8h tiene nada postergable (todas de 1
                # solo cliente ya inviable) — caso degenerado e irresoluble
                # por esta vía; nos quedamos con esta solución.
                break
            nuevos_clientes = [
                c for c in current_instance.clientes if c.id not in client_ids_a_postergar
            ]
            postponed.extend(client_ids_a_postergar)
            current_instance = Instancia(
                id=current_instance.id,
                deposito=current_instance.deposito,
                flota=current_instance.flota,
                clientes=nuevos_clientes,
                created_at=current_instance.created_at,
            )
            continue

        under_5h = any(durations[r.vehicle_id] < 5.0 for r in solution.rutas)
        if under_5h and current_instance.flota.num_vehiculos > 1:
            # Bug real: reducir de a 1 vehículo por vuelta (llamando al
            # solver completo en cada una) requiere tantas vueltas como
            # vehículos sobran — con flotas grandes y muchas rutas cortas
            # (20 motos disponibles para 50 pedidos de un mismo sector, el
            # solver arma solo 6 rutas reales pero ninguna llega a 5h) esto
            # agotaba MAX_REINTENTOS_ORQUESTACION mucho antes de consolidar
            # lo suficiente. Se calcula de una vez cuántos vehículos hacen
            # falta: la suma de horas de TRABAJO real (conducción+espera)
            # de las rutas que el solver ya formó, dividida entre el punto
            # medio del rango válido (6.5h), estima cuántas rutas de ese
            # tamaño hacen falta para la misma carga de hoy — basado en
            # len(solution.rutas) (lo que el solver realmente usó), no en
            # num_vehiculos de la flota disponible (bug de una versión
            # anterior de este fix: con 20 motos disponibles pero solo 6
            # rutas reales, escalar por 20 en vez de por 6 daba un target
            # inflado que nunca bajaba lo suficiente). Nunca baja de golpe
            # a menos de la mitad de la flota actual, dejando que la vuelta
            # siguiente termine de ajustar si hizo falta.
            total_hours = sum(durations.values())
            target_por_horas = max(1, math.ceil(total_hours / 6.5))
            # La estimación por horas ignora capacidad — un target que deja
            # la flota sin espacio para la demanda total (RN-005) hacía que
            # Instancia() rechazara la reducción más abajo y el bucle se
            # rindiera ahí mismo, sin haber consolidado nada. Se calcula
            # también el mínimo de vehículos que sí entra en capacidad
            # (capacidad total actual / vehículo más chico de la flota
            # actual, conservador) y se toma el máximo entre ambos pisos.
            demanda_total = sum(c.demanda for c in current_instance.clientes)
            capacidad_min_vehiculo = (
                min(current_instance.flota.capacidades_vehiculos)
                if current_instance.flota.capacidades_vehiculos
                else current_instance.flota.capacidad_por_vehiculo
            )
            target_por_capacidad = max(1, math.ceil(demanda_total / capacidad_min_vehiculo))
            nuevo_num_vehiculos = max(target_por_horas, target_por_capacidad, len(solution.rutas) // 2, 1)
            nuevo_num_vehiculos = min(nuevo_num_vehiculos, current_instance.flota.num_vehiculos - 1)
            nueva_flota = Flota(
                num_vehiculos=nuevo_num_vehiculos,
                capacidad_por_vehiculo=current_instance.flota.capacidad_por_vehiculo,
                capacidades_vehiculos=(
                    current_instance.flota.capacidades_vehiculos[:nuevo_num_vehiculos]
                    if current_instance.flota.capacidades_vehiculos
                    else None
                ),
            )
            try:
                current_instance = Instancia(
                    id=current_instance.id,
                    deposito=current_instance.deposito,
                    flota=nueva_flota,
                    clientes=current_instance.clientes,
                    created_at=current_instance.created_at,
                )
            except ValueError:
                # Reducir la flota dejó la demanda total sin capacidad
                # suficiente — no es un caso factible para consolidar más;
                # nos quedamos con la última solución válida.
                break
            continue

        # Ni sobra ni excede: converge, no hace falta reintentar.
        break

    return solution, used_osrm, postponed


def solve_instance(instance: Instancia) -> Tuple[Solucion, bool]:
    """
    Convenience function: Solver una instancia y retornar solución.

    Args:
        instance: Instancia VRP (validated)

    Returns:
        (Solucion, used_osrm): Solución validada, y si el costo/secuencia se
        calcularon con distancias reales de calles (OSRM) o con fallback
        euclídeo. Bug real (Ronda 13, ciclo nuevo, dueño y operario,
        encontrado independientemente por ambos): el orchestrator ya
        registraba esta degradación en self.log, pero se descartaba acá — el
        costo mostrado al usuario era indistinguible de un cálculo con calles
        reales, aunque en realidad el solver optimizó contra línea recta.

    Raises:
        ValueError: Si no hay solución factible
    """
    orchestrator = SolverOrchestrator(instance)
    solucion = orchestrator.solve()
    used_osrm = any(line.startswith("Cost matrix: OSRM") for line in orchestrator.log)
    return solucion, used_osrm
