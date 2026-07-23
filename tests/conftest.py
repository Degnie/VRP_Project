"""
Pytest configuration and shared fixtures
"""

import pytest
from backend_python.models import Cliente, Instancia

@pytest.fixture
def small_instance():
    """Fixture: small instance (10 clients)"""
    clientes = [
        Cliente(id=0, x=0.0, y=0.0, demanda=0),  # depot
        Cliente(id=1, x=1.0, y=1.0, demanda=5),
        Cliente(id=2, x=2.0, y=2.0, demanda=5),
        Cliente(id=3, x=3.0, y=3.0, demanda=4),
        Cliente(id=4, x=4.0, y=4.0, demanda=6),
        Cliente(id=5, x=5.0, y=5.0, demanda=8),
        Cliente(id=6, x=6.0, y=6.0, demanda=3),
        Cliente(id=7, x=7.0, y=7.0, demanda=4),
        Cliente(id=8, x=8.0, y=8.0, demanda=7),
        Cliente(id=9, x=9.0, y=9.0, demanda=5),
        Cliente(id=10, x=10.0, y=10.0, demanda=6),
    ]
    return Instancia(clientes=clientes, capacidad_vehiculo=30)

@pytest.fixture
def medium_instance():
    """Fixture: medium instance (100 clients) - TODO: generate"""
    # Placeholder
    return None

@pytest.fixture
def large_instance():
    """Fixture: large instance (1k+ clients) - TODO: generate"""
    # Placeholder
    return None
