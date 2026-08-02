"""Generación de la hoja de ruta en PDF (Etapa 3).

Una página por vehículo: secuencia de paradas con nombre/teléfono/dirección
del cliente cuando están disponibles (el repartidor en la calle los necesita
para confirmar la entrega). reportlab es puro Python — sin dependencias
nativas (GTK/Pango) que weasyprint sí requeriría en Windows.
"""

from io import BytesIO
from typing import Dict, Optional, Set

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

from backend_python.models import Cliente, Solucion

_PLACEHOLDER_UNSUPPORTED_CHARS = "[nombre con caracteres no soportados]"


def _pdf_safe(text: str) -> str:
    """Bug real (Ronda 4, ciclo nuevo, dueño): las fuentes base14 de reportlab
    (Helvetica) solo cubren WinAnsiEncoding (~Latin-1 extendido) — un nombre
    con CJK, cirílico o emoji no lanza excepción, reportlab lo sustituye en
    silencio por una secuencia de 'n' repetidas, indistinguible de un error
    de imprenta hasta que alguien lo lee en el papel que el repartidor usa
    para confirmar la entrega. Se detecta antes de dibujar y se reemplaza
    por un placeholder explícito en vez de dejar la corrupción silenciosa."""
    try:
        text.encode("cp1252")
        return text
    except UnicodeEncodeError:
        return _PLACEHOLDER_UNSUPPORTED_CHARS


def build_route_pdf(
    solution: Solucion,
    clientes_by_id: Dict[int, Cliente],
    vehicle_id: Optional[int] = None,
    rescheduled_client_ids: Optional[Set[int]] = None,
) -> bytes:
    """Arma el PDF de hoja de ruta.

    Una página por vehículo (o solo la de `vehicle_id` si se especifica).

    `rescheduled_client_ids`: bug real (Ronda 48) — reprogramar un pedido lo
    mueve a otra instancia y lo marca "reprogramado" en la original, pero
    `solution.rutas[].secuencia` nunca se recalcula (solo "Resolver de nuevo"
    lo hace), así que sin este filtro el PDF exportado seguía incluyendo esa
    parada como trabajo real — el repartidor iba a una dirección que ya no le
    corresponde, sin ninguna marca en el papel que lo distinga.
    """
    rescheduled_client_ids = rescheduled_client_ids or set()
    rutas = solution.rutas
    if vehicle_id is not None:
        rutas = [r for r in rutas if r.vehicle_id == vehicle_id]

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    # Sin compresión: permite verificar el PDF por conteo de bytes en tests
    # ("/Type /Page", nombre del cliente) sin depender de una librería de
    # parseo de PDF — el archivo es chico (hojas de ruta), el costo es nulo.
    pdf.setPageCompression(0)
    width, height = A4
    margin = 2 * cm

    for ruta in rutas:
        y = height - margin
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, y, f"Hoja de ruta — Vehículo {ruta.vehicle_id + 1}")
        y -= 0.8 * cm
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margin, y, f"Instancia: {solution.instancia_id}  ·  Distancia ruta: {ruta.costo / 1000:.1f} km")
        y -= 1.2 * cm

        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(margin, y, "Parada")
        pdf.drawString(margin + 1.5 * cm, y, "Cliente")
        pdf.drawString(margin + 8 * cm, y, "Teléfono")
        pdf.drawString(margin + 11 * cm, y, "Dirección")
        y -= 0.5 * cm
        pdf.line(margin, y, width - margin, y)
        y -= 0.6 * cm

        pdf.setFont("Helvetica", 9)
        stop_num = 0
        for client_id in ruta.secuencia:
            if client_id in rescheduled_client_ids:
                continue
            stop_num += 1
            if y < margin:
                pdf.showPage()
                y = height - margin
                pdf.setFont("Helvetica", 9)

            cliente = clientes_by_id.get(client_id)
            name = _pdf_safe(cliente.customer_name if cliente and cliente.customer_name else f"Cliente {client_id}")
            phone = _pdf_safe(cliente.customer_phone if cliente and cliente.customer_phone else "—")
            address = _pdf_safe(cliente.address if cliente and cliente.address else "—")

            pdf.drawString(margin, y, str(stop_num))
            pdf.drawString(margin + 1.5 * cm, y, name[:35])
            pdf.drawString(margin + 8 * cm, y, phone[:20])
            pdf.drawString(margin + 11 * cm, y, address[:40])
            y -= 0.5 * cm

        pdf.showPage()

    pdf.save()
    return buffer.getvalue()


__all__ = ["build_route_pdf"]
