"""
Tests para entidades de dominio: Instancia, Cliente, Solución, Ruta.
TDD-first: invariantes, validación, serialización.
"""

import pytest
from backend_python.models import (
    Coordinate, Cliente, Deposito, Flota, Instancia,
    Ruta, Solucion, distancia_euclidiana
)


class TestCoordinate:
    """Validación de coordenadas (x, y)."""

    def test_valid_coordinates(self):
        """Coordenadas positivas válidas."""
        coord = Coordinate(x=10.5, y=20.3)
        assert coord.x == 10.5
        assert coord.y == 20.3

    def test_zero_coordinates(self):
        """Origen (0,0) válido."""
        coord = Coordinate(x=0.0, y=0.0)
        assert coord.x == 0.0

    def test_negative_coordinates_allowed(self):
        """Coordenadas negativas permitidas (sistema SIG)."""
        coord = Coordinate(x=-73.9352, y=40.7306)  # NYC
        assert coord.x < 0


class TestCliente:
    """Validación de Cliente: demanda y ubicación."""

    def test_cliente_valid(self):
        """Cliente válido."""
        client = Cliente(
            id=1,
            coordenada=Coordinate(x=10.0, y=20.0),
            demanda=100
        )
        assert client.id == 1
        assert client.demanda == 100

    def test_cliente_demanda_must_be_positive(self):
        """Invariante: demanda > 0."""
        with pytest.raises(ValueError, match="demanda debe ser positiva"):
            Cliente(
                id=1,
                coordenada=Coordinate(x=10.0, y=20.0),
                demanda=0  # ❌
            )

    def test_cliente_demanda_cannot_be_negative(self):
        """Invariante: demanda > 0 (nunca negativa)."""
        with pytest.raises(ValueError, match="demanda debe ser positiva"):
            Cliente(
                id=1,
                coordenada=Coordinate(x=10.0, y=20.0),
                demanda=-50  # ❌
            )


class TestDepositoFlota:
    """Configuración del depósito y flota."""

    def test_depot_valid(self):
        """Depósito válido."""
        depot = Deposito(
            coordenada=Coordinate(x=0.0, y=0.0),
            nombre="Main Warehouse"
        )
        assert depot.nombre == "Main Warehouse"

    def test_flota_capacidad_positiva(self):
        """Invariante: capacidad de vehículo > 0."""
        with pytest.raises(ValueError, match="capacidad debe ser positiva"):
            Flota(
                num_vehiculos=5,
                capacidad_por_vehiculo=0  # ❌
            )

    def test_flota_num_vehiculos_positivo(self):
        """Invariante: num_vehiculos >= 1."""
        with pytest.raises(ValueError, match="num_vehiculos debe ser >= 1"):
            Flota(
                num_vehiculos=0,  # ❌
                capacidad_por_vehiculo=1000
            )


class TestInstancia:
    """Agregado: Instancia (depósito + flota + clientes)."""

    def test_instancia_valid_simple(self):
        """Instancia válida con 2 clientes."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=1000)
        clientes = [
            Cliente(1, Coordinate(10.0, 10.0), 100),
            Cliente(2, Coordinate(20.0, 20.0), 150),
        ]

        instance = Instancia(
            id="inst_1",
            deposito=depot,
            flota=flota,
            clientes=clientes
        )

        assert instance.id == "inst_1"
        assert len(instance.clientes) == 2
        assert instance.flota.capacidad_por_vehiculo == 1000

    def test_instancia_demanda_total_no_excede_capacidad_total(self):
        """Invariante: sum(demandas) <= flota_capacity * num_vehiculos."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=1, capacidad_por_vehiculo=100)
        clientes = [
            Cliente(1, Coordinate(10.0, 10.0), 60),
            Cliente(2, Coordinate(20.0, 20.0), 60),  # 60 + 60 = 120 > 100 ❌
        ]

        with pytest.raises(ValueError, match="demanda total excede capacidad"):
            Instancia(
                id="inst_invalid",
                deposito=depot,
                flota=flota,
                clientes=clientes
            )

    def test_instancia_cliente_ids_unicas(self):
        """Invariante: cada cliente tiene ID único."""
        depot = Deposito(Coordinate(0.0, 0.0), "Depot")
        flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=1000)
        clientes = [
            Cliente(1, Coordinate(10.0, 10.0), 100),
            Cliente(1, Coordinate(20.0, 20.0), 100),  # ❌ ID duplicado
        ]

        with pytest.raises(ValueError, match="IDs de clientes no son únicos"):
            Instancia(
                id="inst_dup",
                deposito=depot,
                flota=flota,
                clientes=clientes
            )


class TestRuta:
    """Ruta: secuencia de clientes para un vehículo."""

    def test_ruta_valid(self):
        """Ruta válida."""
        ruta = Ruta(
            vehicle_id=0,
            secuencia=[1, 2, 3],  # IDs de clientes
            costo=150.5
        )

        assert ruta.vehicle_id == 0
        assert len(ruta.secuencia) == 3
        assert ruta.costo == 150.5

    def test_ruta_secuencia_no_vacia(self):
        """Invariante: secuencia no puede estar vacía."""
        with pytest.raises(ValueError, match="secuencia debe tener al menos 1 cliente"):
            Ruta(
                vehicle_id=0,
                secuencia=[],  # ❌
                costo=0.0
            )

    def test_ruta_costo_no_negativo(self):
        """Invariante: costo >= 0."""
        with pytest.raises(ValueError, match="costo no puede ser negativo"):
            Ruta(
                vehicle_id=0,
                secuencia=[1, 2],
                costo=-10.0  # ❌
            )


class TestSolucion:
    """Solución: conjunto de rutas con costo total."""

    def test_solucion_valid(self):
        """Solución válida."""
        rutas = [
            Ruta(vehicle_id=0, secuencia=[1, 2], costo=100.0),
            Ruta(vehicle_id=1, secuencia=[3, 4], costo=150.0),
        ]

        solucion = Solucion(
            instancia_id="inst_1",
            rutas=rutas,
            costo_total=250.0
        )

        assert solucion.costo_total == 250.0
        assert len(solucion.rutas) == 2

    def test_solucion_costo_total_suma_rutas(self):
        """Invariante: costo_total == sum(ruta.costo)."""
        rutas = [
            Ruta(vehicle_id=0, secuencia=[1, 2], costo=100.0),
            Ruta(vehicle_id=1, secuencia=[3, 4], costo=150.0),
        ]

        # costo_total = 200.0, pero rutas suman 250.0 ❌
        with pytest.raises(ValueError, match="costo_total no coincide con suma de rutas"):
            Solucion(
                instancia_id="inst_1",
                rutas=rutas,
                costo_total=200.0  # ❌ Debería ser 250.0
            )

    def test_solucion_rutas_no_vacias(self):
        """Invariante: solución debe tener al menos 1 ruta."""
        with pytest.raises(ValueError, match="solución debe tener al menos 1 ruta"):
            Solucion(
                instancia_id="inst_1",
                rutas=[],  # ❌
                costo_total=0.0
            )

    def test_solucion_clientes_visitados_una_sola_vez(self):
        """Invariante: cada cliente visitado exactamente 1 vez."""
        rutas = [
            Ruta(vehicle_id=0, secuencia=[1, 2], costo=100.0),
            Ruta(vehicle_id=1, secuencia=[2, 3], costo=150.0),  # ❌ Cliente 2 visitado dos veces
        ]

        with pytest.raises(ValueError, match="cliente visitado múltiples veces"):
            Solucion(
                instancia_id="inst_1",
                rutas=rutas,
                costo_total=250.0
            )


class TestDistanciaEuclidiana:
    """Utilidad: cálculo de distancia euclidiana."""

    def test_distancia_origen_punto(self):
        """Distancia de (0,0) a (3,4)."""
        d = distancia_euclidiana(
            Coordinate(0.0, 0.0),
            Coordinate(3.0, 4.0)
        )
        assert abs(d - 5.0) < 1e-6  # 3-4-5 triangle

    def test_distancia_simetrica(self):
        """Propiedad: dist(A,B) == dist(B,A)."""
        a = Coordinate(1.0, 2.0)
        b = Coordinate(4.0, 6.0)

        d_ab = distancia_euclidiana(a, b)
        d_ba = distancia_euclidiana(b, a)

        assert abs(d_ab - d_ba) < 1e-6

    def test_distancia_mismo_punto_es_cero(self):
        """Propiedad: dist(A,A) == 0."""
        a = Coordinate(5.0, 7.0)
        d = distancia_euclidiana(a, a)
        assert d == 0.0
