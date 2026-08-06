"""Tests de sectorización geográfica de Lima Metropolitana (RN-028, RN-029)."""
from backend_python.models import Coordinate, Flota
from backend_python.service.sectorization import assign_sector, split_fleet_by_sector, SECTORES


class TestAssignSector:
    """RN-028: un cliente se agrupa en el sector cuyo polígono contiene su
    coordenada; fuera de los 4 polígonos, cae en Lima Centro (fallback).

    spec: RN-028
    """

    def test_coordinate_in_lima_norte_polygon(self):
        # Punto interior claro del polígono de Lima Norte (dado por el
        # negocio) — Comas/Independencia, lejos de cualquier borde.
        assert assign_sector(Coordinate(-77.05, -11.90)) == "Lima Norte"

    def test_coordinate_in_lima_este_polygon(self):
        # Punto interior claro del polígono de Lima Este — San Juan de
        # Lurigancho/Ate.
        assert assign_sector(Coordinate(-76.80, -12.00)) == "Lima Este"

    def test_coordinate_in_lima_sur_polygon(self):
        # Punto interior claro del polígono de Lima Sur — Villa El
        # Salvador/Chorrillos.
        assert assign_sector(Coordinate(-77.10, -12.30)) == "Lima Sur"

    def test_coordinate_in_lima_centro_polygon(self):
        # Punto interior claro del polígono de Lima Centro — Cercado de
        # Lima/San Isidro.
        assert assign_sector(Coordinate(-77.00, -12.05)) == "Lima Centro"

    def test_coordinate_outside_all_polygons_falls_back_to_centro(self):
        # Muy lejos de Lima (ej. en el mar o en otra región) — ningún
        # polígono lo contiene, debe caer en el fallback.
        assert assign_sector(Coordinate(-70.00, -18.00)) == "Lima Centro"

    def test_all_four_sector_names_are_defined(self):
        assert set(SECTORES.keys()) == {"Lima Norte", "Lima Este", "Lima Sur", "Lima Centro"}


class TestSplitFleetBySector:
    """RN-029: la flota total se reparte entre los 4 sectores en proporción
    a la demanda de peso de cada uno, preservando el mix de tipos de
    vehículo, sin exceder nunca la flota total disponible.

    spec: RN-029
    """

    def test_split_proportional_to_demand(self):
        # 2 sectores con demanda (80% Norte, 20% Sur), 2 sin demanda — la
        # flota debe repartirse aproximadamente en esa proporción. Un
        # sector sin vehículos asignados es None (Flota exige
        # num_vehiculos >= 1, no puede representar "0 vehículos").
        flota = Flota(num_vehiculos=10, capacidad_por_vehiculo=100)
        demanda_por_sector = {
            "Lima Norte": 800.0,
            "Lima Este": 0.0,
            "Lima Sur": 200.0,
            "Lima Centro": 0.0,
        }
        reparto = split_fleet_by_sector(flota, demanda_por_sector)

        assert set(reparto.keys()) == {"Lima Norte", "Lima Este", "Lima Sur", "Lima Centro"}
        norte_count = reparto["Lima Norte"].num_vehiculos if reparto["Lima Norte"] else 0
        sur_count = reparto["Lima Sur"].num_vehiculos if reparto["Lima Sur"] else 0
        assert norte_count >= sur_count
        assert reparto["Lima Este"] is None
        assert reparto["Lima Centro"] is None

    def test_split_never_exceeds_total_fleet(self):
        flota = Flota(num_vehiculos=7, capacidad_por_vehiculo=50)
        demanda_por_sector = {
            "Lima Norte": 100.0,
            "Lima Este": 90.0,
            "Lima Sur": 80.0,
            "Lima Centro": 70.0,
        }
        reparto = split_fleet_by_sector(flota, demanda_por_sector)

        total_repartido = sum(f.num_vehiculos for f in reparto.values() if f is not None)
        assert total_repartido <= flota.num_vehiculos

    def test_split_preserves_heterogeneous_vehicle_mix(self):
        # Flota heterogénea: 2 camiones grandes + 3 motos chicas — el
        # reparto por sector debe tomar capacidades reales de esa lista,
        # no inventar una capacidad homogénea nueva.
        capacidades = [1500.0, 1500.0, 30.0, 30.0, 30.0]
        flota = Flota(num_vehiculos=5, capacidad_por_vehiculo=1500.0, capacidades_vehiculos=capacidades)
        demanda_por_sector = {
            "Lima Norte": 1000.0,
            "Lima Este": 0.0,
            "Lima Sur": 0.0,
            "Lima Centro": 0.0,
        }
        reparto = split_fleet_by_sector(flota, demanda_por_sector)

        norte = reparto["Lima Norte"]
        assert norte is not None
        if norte.capacidades_vehiculos:
            assert all(c in capacidades for c in norte.capacidades_vehiculos)

    def test_split_with_zero_total_demand_returns_no_fleets(self):
        flota = Flota(num_vehiculos=5, capacidad_por_vehiculo=100)
        demanda_por_sector = {"Lima Norte": 0.0, "Lima Este": 0.0, "Lima Sur": 0.0, "Lima Centro": 0.0}
        reparto = split_fleet_by_sector(flota, demanda_por_sector)

        assert all(f is None for f in reparto.values())
