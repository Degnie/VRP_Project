"""Entidades de dominio para VRP: Coordinate, Cliente, Deposito, Flota, Instancia, Ruta, Solucion."""

from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass(frozen=True)
class Coordinate:
    """Coordenada (x, y) inmutable."""
    x: float
    y: float


@dataclass(frozen=True)
class Cliente:
    """Cliente: ubicación + demanda + contacto opcional.

    Los campos de contacto no los usa el solver (solo coordenada/demanda) —
    viajan junto a la instancia para poder mostrarlos/imprimirlos en la hoja
    de ruta (el repartidor en la calle necesita nombre/teléfono/dirección
    para confirmar la entrega, no solo un id de cliente).

    Invariantes:
    - demanda > 0
    """
    id: int
    coordenada: Coordinate
    demanda: float
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None
    # updated_at (Ronda 2, ciclo nuevo, operario): snapshot de
    # clientes.updated_at al momento de load_instance() — save_instance lo
    # usa para optimistic locking (no pisar una edición concurrente de
    # update_client con los valores viejos de un solve en curso).
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.demanda <= 0:
            raise ValueError("demanda debe ser positiva")
        if self.demanda != int(self.demanda):
            raise ValueError("demanda debe ser un valor entero")


@dataclass(frozen=True)
class Deposito:
    """Depósito (punto de origen/destino)."""
    coordenada: Coordinate
    nombre: str = "Depot"


@dataclass(frozen=True)
class Flota:
    """Configuración de flota de vehículos.

    capacidades_vehiculos es opcional: si se especifica, el solver asigna
    capacidad[i] al vehículo i (en el orden dado) en vez de repetir
    capacidad_por_vehiculo para toda la flota — soporta flota heterogénea
    real (motos, camionetas, etc. con capacidades distintas).

    Invariantes:
    - num_vehiculos >= 1
    - capacidad_por_vehiculo > 0
    - si capacidades_vehiculos está presente: len == num_vehiculos, todas > 0
    """
    num_vehiculos: int
    capacidad_por_vehiculo: float
    capacidades_vehiculos: Optional[List[float]] = None

    def __post_init__(self):
        if self.num_vehiculos < 1:
            raise ValueError("num_vehiculos debe ser >= 1")
        if self.capacidad_por_vehiculo <= 0:
            raise ValueError("capacidad debe ser positiva")
        if self.capacidades_vehiculos is not None:
            if len(self.capacidades_vehiculos) != self.num_vehiculos:
                raise ValueError("capacidades_vehiculos debe tener num_vehiculos elementos")
            if any(c <= 0 for c in self.capacidades_vehiculos):
                raise ValueError("cada capacidad en capacidades_vehiculos debe ser positiva")

    @property
    def capacidad_total(self) -> float:
        """Capacidad total de la flota, considerando capacidades heterogéneas si aplica."""
        if self.capacidades_vehiculos is not None:
            return sum(self.capacidades_vehiculos)
        return self.num_vehiculos * self.capacidad_por_vehiculo


@dataclass(frozen=True)
class Instancia:
    """Instancia VRP: depósito + flota + clientes.
    Invariantes:
    - IDs de clientes únicos
    - sum(demandas) <= num_vehiculos * capacidad
    """
    id: str
    deposito: Deposito
    flota: Flota
    clientes: List[Cliente]
    created_at: Optional[str] = None  # ISO 8601; None si no viene de persistencia

    def __post_init__(self):
        # Verificar IDs únicos
        ids = [c.id for c in self.clientes]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de clientes no son únicos")

        # Verificar demanda total
        demanda_total = sum(c.demanda for c in self.clientes)
        if demanda_total > self.flota.capacidad_total:
            raise ValueError("demanda total excede capacidad de la flota")

        # Un cliente cuya demanda excede el vehículo más grande de la flota es
        # irresoluble aunque la demanda TOTAL entre — ni el fallback Python ni
        # el builder NearestNeighbor de C++ dejan un cliente sin visitar (el de
        # C++ queda en un `while(true)` sin salida, colgando el proceso). Se
        # corta acá, antes de llegar a cualquiera de los dos solvers.
        max_capacidad_vehiculo = (
            max(self.flota.capacidades_vehiculos)
            if self.flota.capacidades_vehiculos
            else self.flota.capacidad_por_vehiculo
        )
        sobrepasados = [c.id for c in self.clientes if c.demanda > max_capacidad_vehiculo]
        if sobrepasados:
            raise ValueError(
                f"cliente(s) {sobrepasados} tienen demanda mayor a la capacidad de "
                f"cualquier vehículo disponible ({max_capacidad_vehiculo})"
            )


@dataclass(frozen=True)
class Ruta:
    """Ruta: secuencia de clientes para un vehículo.
    Invariantes:
    - secuencia no vacía
    - costo >= 0
    """
    vehicle_id: int
    secuencia: List[int]  # IDs de clientes
    costo: float

    def __post_init__(self):
        if not self.secuencia:
            raise ValueError("secuencia debe tener al menos 1 cliente")
        if self.costo < 0:
            raise ValueError("costo no puede ser negativo")


@dataclass(frozen=True)
class Solucion:
    """Solución: conjunto de rutas.
    Invariantes:
    - Al menos 1 ruta
    - costo_total == sum(ruta.costo)
    - Cada cliente visitado exactamente una vez
    """
    instancia_id: str
    rutas: List[Ruta]
    costo_total: float

    def __post_init__(self):
        if not self.rutas:
            raise ValueError("solución debe tener al menos 1 ruta")

        # Verificar costo_total
        suma_costos = sum(r.costo for r in self.rutas)
        if abs(self.costo_total - suma_costos) > 1e-6:
            raise ValueError("costo_total no coincide con suma de rutas")

        # Verificar que cada cliente se visita una sola vez
        todos_clientes = []
        for ruta in self.rutas:
            todos_clientes.extend(ruta.secuencia)

        if len(todos_clientes) != len(set(todos_clientes)):
            raise ValueError("cliente visitado múltiples veces")


def distancia_euclidiana(a: Coordinate, b: Coordinate) -> float:
    """Distancia euclidiana entre dos coordenadas."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


__all__ = [
    "Coordinate",
    "Cliente",
    "Deposito",
    "Flota",
    "Instancia",
    "Ruta",
    "Solucion",
    "distancia_euclidiana",
]
