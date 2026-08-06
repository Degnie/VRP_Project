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
    a la CANTIDAD DE CLIENTES de cada uno (proxy de carga horaria — RN-026
    estima tiempo por cantidad de paradas, no por peso transportado),
    preservando el mix de tipos de vehículo, sin exceder nunca la flota
    total disponible.

    spec: RN-029
    """

    def test_split_proportional_to_client_count(self):
        # 2 sectores con clientes (80% Norte, 20% Sur), 2 sin clientes — la
        # flota debe repartirse aproximadamente en esa proporción. Un
        # sector sin vehículos asignados es None (Flota exige
        # num_vehiculos >= 1, no puede representar "0 vehículos").
        flota = Flota(num_vehiculos=10, capacidad_por_vehiculo=100)
        num_clientes_por_sector = {
            "Lima Norte": 80,
            "Lima Este": 0,
            "Lima Sur": 20,
            "Lima Centro": 0,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        assert set(reparto.keys()) == {"Lima Norte", "Lima Este", "Lima Sur", "Lima Centro"}
        norte_count = reparto["Lima Norte"].num_vehiculos if reparto["Lima Norte"] else 0
        sur_count = reparto["Lima Sur"].num_vehiculos if reparto["Lima Sur"] else 0
        assert norte_count >= sur_count
        assert reparto["Lima Este"] is None
        assert reparto["Lima Centro"] is None

    def test_split_never_exceeds_total_fleet(self):
        flota = Flota(num_vehiculos=7, capacidad_por_vehiculo=50)
        num_clientes_por_sector = {
            "Lima Norte": 10,
            "Lima Este": 9,
            "Lima Sur": 8,
            "Lima Centro": 7,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        total_repartido = sum(f.num_vehiculos for f in reparto.values() if f is not None)
        assert total_repartido <= flota.num_vehiculos

    def test_split_preserves_heterogeneous_vehicle_mix(self):
        # Flota heterogénea: 2 camiones grandes + 3 motos chicas — el
        # reparto por sector debe tomar capacidades reales de esa lista,
        # no inventar una capacidad homogénea nueva.
        capacidades = [1500.0, 1500.0, 30.0, 30.0, 30.0]
        flota = Flota(num_vehiculos=5, capacidad_por_vehiculo=1500.0, capacidades_vehiculos=capacidades)
        num_clientes_por_sector = {
            "Lima Norte": 20,
            "Lima Este": 0,
            "Lima Sur": 0,
            "Lima Centro": 0,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        norte = reparto["Lima Norte"]
        assert norte is not None
        if norte.capacidades_vehiculos:
            assert all(c in capacidades for c in norte.capacidades_vehiculos)

    def test_split_with_zero_total_clients_returns_no_fleets(self):
        flota = Flota(num_vehiculos=5, capacidad_por_vehiculo=100)
        num_clientes_por_sector = {"Lima Norte": 0, "Lima Este": 0, "Lima Sur": 0, "Lima Centro": 0}
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        assert all(f is None for f in reparto.values())

    def test_every_sector_with_clients_gets_at_least_one_vehicle(self):
        """RN-029: con flota chica (4 vehículos, 4 sectores con clientes), el
        reparto proporcional puro (math.floor) podía dejar un sector con
        pocos clientes pero > 0 en 0 vehículos — quedaba completamente sin
        ruta. Cada sector con clientes > 0 debe recibir garantizado 1
        vehículo antes del reparto proporcional del resto.

        Bug real reportado: con una flota de 4 vehículos y clientes muy
        desiguales entre sectores (ej. Lima Este con pocos clientes
        relativos), Lima Este quedaba en 0 vehículos — todos sus clientes
        se descartaban/postergaban sin generar ninguna ruta.

        spec: RN-029
        """
        flota = Flota(num_vehiculos=4, capacidad_por_vehiculo=1000)
        num_clientes_por_sector = {
            "Lima Norte": 97,
            "Lima Este": 1,
            "Lima Sur": 1,
            "Lima Centro": 1,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        for nombre, num_clientes in num_clientes_por_sector.items():
            if num_clientes > 0:
                assert reparto[nombre] is not None, f"{nombre} se quedó sin flota pese a tener clientes"
                assert reparto[nombre].num_vehiculos >= 1

    def test_sector_with_no_clients_still_gets_no_fleet(self):
        """El piso de 1 vehículo aplica solo a sectores CON clientes — un
        sector vacío ese día no debe recibir flota desperdiciada."""
        flota = Flota(num_vehiculos=4, capacidad_por_vehiculo=1000)
        num_clientes_por_sector = {
            "Lima Norte": 50,
            "Lima Este": 50,
            "Lima Sur": 0,
            "Lima Centro": 0,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        assert reparto["Lima Sur"] is None
        assert reparto["Lima Centro"] is None

    def test_fewer_vehicles_than_sectors_drops_lowest_client_count_sector(self):
        """Confirmado por el usuario: si hay menos vehículos que sectores
        con clientes, el/los sector(es) de MENOS clientes se quedan sin
        flota — no se inventan vehículos ni se mezclan pedidos entre
        sectores."""
        flota = Flota(num_vehiculos=2, capacidad_por_vehiculo=1000)
        num_clientes_por_sector = {
            "Lima Norte": 50,
            "Lima Este": 30,
            "Lima Sur": 10,
            "Lima Centro": 5,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        total_repartido = sum(f.num_vehiculos for f in reparto.values() if f is not None)
        assert total_repartido <= 2
        assert reparto["Lima Centro"] is None

    def test_split_proportional_to_client_count_not_weight(self):
        """Bug real reportado: un sector con MUCHOS clientes chicos (poco
        peso c/u) necesita más vehículos por CARGA HORARIA (RN-026 estima
        tiempo por cantidad de paradas, ~15min c/u) que uno con pocos
        clientes de mucho peso — repartir por peso podía darle más flota al
        sector equivocado.

        spec: RN-029
        """
        flota = Flota(num_vehiculos=4, capacidad_por_vehiculo=1000)
        # Lima Norte: 1 solo cliente pero con mucho peso.
        # Lima Este: 25 clientes con poco peso cada uno.
        num_clientes_por_sector = {
            "Lima Norte": 1,
            "Lima Este": 25,
            "Lima Sur": 0,
            "Lima Centro": 0,
        }
        reparto = split_fleet_by_sector(flota, num_clientes_por_sector)

        este_count = reparto["Lima Este"].num_vehiculos if reparto["Lima Este"] else 0
        norte_count = reparto["Lima Norte"].num_vehiculos if reparto["Lima Norte"] else 0
        assert este_count > norte_count
