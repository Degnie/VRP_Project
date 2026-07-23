"""
Modelos de Dominio: Instancia, Cliente, Solución, Ruta

Estas entidades encapsulan la lógica del dominio VRP.
Los algoritmos en C++ operan sobre estructuras de bajo nivel,
pero siempre a través de estos modelos.
"""

from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Cliente:
    """Representa un cliente con ubicación y demanda."""
    id: int
    x: float
    y: float
    demanda: int

    def __post_init__(self):
        if self.demanda < 0:
            raise ValueError(f"Demanda debe ser positiva: {self.demanda}")

@dataclass
class Instancia:
    """Configuración completa del problema VRP."""
    clientes: List[Cliente]
    capacidad_vehiculo: int
    deposito_id: int = 0

    def __post_init__(self):
        if self.capacidad_vehiculo <= 0:
            raise ValueError(f"Capacidad debe ser positiva: {self.capacidad_vehiculo}")
        if not any(c.id == self.deposito_id for c in self.clientes):
            raise ValueError(f"Depósito {self.deposito_id} no existe en clientes")

    @property
    def n_clientes(self) -> int:
        return len(self.clientes)

@dataclass
class Ruta:
    """Secuencia de clientes visitados por un vehículo."""
    vehiculo_id: int
    secuencia: List[int]  # IDs de clientes, incluyendo depot al inicio y fin
    costo: float = 0.0

    def validar(self, instancia: Instancia) -> bool:
        """Verificar invariantes de ruta."""
        # TODO: Implementar validación
        return True

@dataclass
class Solucion:
    """Solución completa al problema VRP."""
    rutas: List[Ruta]
    costo_total: float
    es_valida: bool = True

    def validar(self, instancia: Instancia) -> bool:
        """Verificar invariantes de solución."""
        # TODO: Implementar validación de capacidad, cobertura, etc.
        return True

__all__ = ["Cliente", "Instancia", "Ruta", "Solucion"]
