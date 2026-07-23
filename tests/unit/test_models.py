"""
Unit tests para modelos de dominio
"""

import pytest
from backend_python.models import Cliente, Instancia, Ruta, Solucion

class TestCliente:
    def test_cliente_creation(self):
        c = Cliente(id=1, x=1.0, y=2.0, demanda=5)
        assert c.id == 1
        assert c.demanda == 5
    
    def test_cliente_negative_demand_invalid(self):
        with pytest.raises(ValueError):
            Cliente(id=1, x=1.0, y=2.0, demanda=-1)

class TestInstancia:
    def test_instancia_creation(self, small_instance):
        assert small_instance.n_clientes == 11
        assert small_instance.capacidad_vehiculo == 30
    
    def test_instancia_invalid_capacity(self, small_instance):
        with pytest.raises(ValueError):
            Instancia(
                clientes=small_instance.clientes,
                capacidad_vehiculo=-1
            )
