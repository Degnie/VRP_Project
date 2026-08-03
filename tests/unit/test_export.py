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
    """spec: CU-EXP-001, RN-EXP-001"""

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

    def test_name_with_unsupported_charset_uses_explicit_placeholder(self):
        """Bug real (Ronda 4, ciclo nuevo, dueño): un nombre con CJK/cirílico/
        emoji no lanza excepción con las fuentes base14 (Helvetica,
        WinAnsiEncoding) — reportlab lo sustituye en silencio por una
        secuencia de 'n' repetidas, indistinguible de un error de imprenta
        hasta que alguien lo lee en el papel. Se detecta antes de dibujar y
        se reemplaza por un placeholder explícito."""
        rutas = [Ruta(vehicle_id=0, secuencia=[1], costo=1.0)]
        solution = Solucion(instancia_id="pdf-unicode", rutas=rutas, costo_total=1.0)
        clientes_by_id = {
            1: Cliente(1, Coordinate(0, 0), 10, customer_name="日本語のテスト"),
        }
        pdf = build_route_pdf(solution, clientes_by_id)
        assert pdf.startswith(b"%PDF-")
        # truncado a 35 chars (mismo límite que cualquier nombre largo, ver
        # name[:35] en build_route_pdf) — el placeholder completo no entra.
        assert b"nombre con caracteres no soportad" in pdf

    def test_vehicle_with_all_stops_rescheduled_shows_explicit_message(self):
        """Bug real (Ronda 3, ciclo 3, dueño): si se reprograma el 100% de los
        pedidos de un vehículo, el filtro de rescheduled_client_ids deja la
        página sin ninguna fila — RN-EXP-002 solo exige que el vehículo tenga
        alguna ruta en la solución original, así que salía 200 con encabezado
        y columnas pero cero paradas, indistinguible de un error de generación."""
        rutas = [Ruta(vehicle_id=0, secuencia=[1, 2], costo=1.0)]
        solution = Solucion(instancia_id="pdf-all-rescheduled", rutas=rutas, costo_total=1.0)
        pdf = build_route_pdf(solution, _clientes_by_id(), rescheduled_client_ids={1, 2})
        assert pdf.startswith(b"%PDF-")
        assert b"reprogramados" in pdf
