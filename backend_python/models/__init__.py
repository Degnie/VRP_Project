"""Entidades de dominio para VRP: Coordinate, Cliente, Deposito, Flota, Instancia, Ruta, Solucion."""

from dataclasses import dataclass
from typing import List
import math


@dataclass(frozen=True)
class Coordinate:
    """Coordenada (x, y) inmutable."""
    x: float
    y: float


@dataclass(frozen=True)
class Cliente:
    """Cliente: ubicación + demanda.
    Invariantes:
    - demanda > 0
    """
    id: int
    coordenada: Coordinate
    demanda: float

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
    Invariantes:
    - num_vehiculos >= 1
    - capacidad_por_vehiculo > 0
    """
    num_vehiculos: int
    capacidad_por_vehiculo: float

    def __post_init__(self):
        if self.num_vehiculos < 1:
            raise ValueError("num_vehiculos debe ser >= 1")
        if self.capacidad_por_vehiculo <= 0:
            raise ValueError("capacidad debe ser positiva")


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

    def __post_init__(self):
        # Verificar IDs únicos
        ids = [c.id for c in self.clientes]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de clientes no son únicos")

        # Verificar demanda total
        demanda_total = sum(c.demanda for c in self.clientes)
        capacidad_total = self.flota.num_vehiculos * self.flota.capacidad_por_vehiculo
        if demanda_total > capacidad_total:
            raise ValueError("demanda total excede capacidad de la flota")


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
