"""Tests unitarios de build_route_pdf (puro, sin DB)."""

from backend_python.api.export import build_route_pdf
from backend_python.models import Cliente, Coordinate, Ruta, Solucion


def _solution_with_two_vehicles():
    rutas = [
        Ruta(vehicle_id=0, secuencia=[1, 2], costo=10.0),
        Ruta(vehicle_id=1, secuencia=[3], costo=5.0),
    ]
    return Solucion(instancia_id="pdf-test", rutas=rutas, costo_total=15.0)


def _clientes_by_id():
    return {
        1: Cliente(1, Coordinate(0, 0), 10, customer_name="Ana", customer_phone="999", address="Av. 1"),
        2: Cliente(2, Coordinate(1, 1), 10),
        3: Cliente(3, Coordinate(2, 2), 5, customer_name="Beto"),
    }


class TestBuildRoutePdf:
    def test_produces_valid_pdf_bytes(self):
        pdf = build_route_pdf(_solution_with_two_vehicles(), _clientes_by_id())
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 0

    def test_one_page_per_vehicle_when_no_filter(self):
        pdf = build_route_pdf(_solution_with_two_vehicles(), _clientes_by_id())
        # "/Type /Page\n", no "/Type /Page" — evita el falso positivo de matchear
        # "/Type /Pages" (el nodo padre del árbol de páginas, que también empieza así).
        assert pdf.count(b"/Type /Page\n") == 2

    def test_filters_by_vehicle_id(self):
        pdf = build_route_pdf(_solution_with_two_vehicles(), _clientes_by_id(), vehicle_id=1)
        assert pdf.count(b"/Type /Page\n") == 1

    def test_missing_client_falls_back_to_generic_label(self):
        # cliente_id 99 no está en el dict — no debe explotar, usa "Cliente 99".
        rutas = [Ruta(vehicle_id=0, secuencia=[99], costo=1.0)]
        solution = Solucion(instancia_id="pdf-missing", rutas=rutas, costo_total=1.0)
        pdf = build_route_pdf(solution, {})
        assert pdf.startswith(b"%PDF-")
