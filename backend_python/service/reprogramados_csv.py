"""CSV de pendientes de reprogramación por cuenta (RN-031, RN-032, RN-034).

Un archivo `reprogramados_{account_id}.csv` por cuenta, en REPROGRAMADOS_DIR.
No hay reprogramación automática en DB: el operario decide cuándo mezclar
estos pendientes en la instancia del día (ver GET/POST /reprogramados en la API).

Cada fila guarda el snapshot completo del pedido (coordenadas, demanda,
contacto), no solo su id — cliente.id no es único global (se reusa 1,2,3...
en cada instancia nueva), y la instancia original puede haber sido borrada
para cuando el operario decide mezclarlo. El CSV debe ser autosuficiente.
"""
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class ReprogramadoRow:
    cliente_id: int
    priority: int
    force_include: bool
    x: float
    y: float
    demand: float
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    address: Optional[str] = None


_FIELDS = [
    "cliente_id", "priority", "force_include", "x", "y", "demand",
    "customer_name", "customer_phone", "address",
]


def _path(base_dir: str, account_id: str) -> Path:
    return Path(base_dir) / f"reprogramados_{account_id}.csv"


def csv_path(base_dir: str, account_id: str) -> Optional[Path]:
    """RN-035: ruta al archivo real en disco, para servirlo como descarga.
    None si la cuenta no tiene reprogramados pendientes."""
    path = _path(base_dir, account_id)
    return path if path.exists() else None


def read_pending(base_dir: str, account_id: str) -> List[ReprogramadoRow]:
    path = _path(base_dir, account_id)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return [
            ReprogramadoRow(
                cliente_id=int(row["cliente_id"]),
                priority=int(row["priority"]),
                force_include=row["force_include"] == "True",
                x=float(row["x"]),
                y=float(row["y"]),
                demand=float(row["demand"]),
                customer_name=row["customer_name"] or None,
                customer_phone=row["customer_phone"] or None,
                address=row["address"] or None,
            )
            for row in csv.DictReader(f)
        ]


def _write(base_dir: str, account_id: str, rows: List[ReprogramadoRow]) -> None:
    path = _path(base_dir, account_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "cliente_id": row.cliente_id, "priority": row.priority, "force_include": row.force_include,
                    "x": row.x, "y": row.y, "demand": row.demand,
                    "customer_name": row.customer_name or "", "customer_phone": row.customer_phone or "",
                    "address": row.address or "",
                }
            )


def upsert(base_dir: str, account_id: str, rows: List[ReprogramadoRow]) -> None:
    """Agrega/actualiza clientes no entregados (RN-031). priority tope 1
    (RN-032): si el cliente ya estaba en el CSV, no sube más allá de 1 y se
    marca force_include=true en su lugar. El snapshot (coordenadas/contacto)
    se refresca con el más reciente en cada llamada."""
    existing = {row.cliente_id: row for row in read_pending(base_dir, account_id)}
    for incoming in rows:
        current = existing.get(incoming.cliente_id)
        if current is None:
            incoming.priority = 1
            incoming.force_include = False
            existing[incoming.cliente_id] = incoming
        else:
            incoming.priority = current.priority
            incoming.force_include = True
            existing[incoming.cliente_id] = incoming
    _write(base_dir, account_id, list(existing.values()))


def remove(base_dir: str, account_id: str, cliente_ids: List[int]) -> None:
    """RN-034: borra únicamente las filas de los ids dados."""
    path = _path(base_dir, account_id)
    if not path.exists():
        return
    to_remove = set(cliente_ids)
    remaining = [row for row in read_pending(base_dir, account_id) if row.cliente_id not in to_remove]
    _write(base_dir, account_id, remaining)


__all__ = ["ReprogramadoRow", "read_pending", "upsert", "remove", "csv_path"]
