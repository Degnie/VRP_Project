"""Tests del CSV de reprogramados por cuenta (RN-031, RN-032, RN-034)."""
import tempfile

import pytest

from backend_python.service.reprogramados_csv import (
    ReprogramadoRow,
    read_pending,
    remove,
    upsert,
)


def _row(cliente_id, priority=0, force_include=False, x=1.0, y=2.0, demand=10.0, name="Ana"):
    return ReprogramadoRow(
        cliente_id=cliente_id, priority=priority, force_include=force_include,
        x=x, y=y, demand=demand,
        customer_name=name, customer_phone="999", address="Av. Siempre Viva",
    )


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestUpsertAndRead:
    def test_new_client_starts_at_priority_1(self, tmp_dir):
        """RN-031: un cliente no entregado se agrega al CSV con priority=1,
        conservando su snapshot completo (coordenadas/demanda/contacto) para
        poder reconstruirlo sin depender de la instancia original.

        spec: RN-031
        """
        upsert(tmp_dir, "acc1", [_row(5, x=10.0, y=20.0, demand=30.0, name="Ana")])
        rows = read_pending(tmp_dir, "acc1")
        assert len(rows) == 1
        assert rows[0].cliente_id == 5
        assert rows[0].priority == 1
        assert rows[0].force_include is False
        assert rows[0].x == 10.0
        assert rows[0].y == 20.0
        assert rows[0].demand == 30.0
        assert rows[0].customer_name == "Ana"

    def test_existing_client_priority_capped_at_1(self, tmp_dir):
        """RN-032: un cliente que ya tiene priority=1 y vuelve a fallar no
        sube a 2 — se marca force_include=true en su lugar.

        spec: RN-032
        """
        upsert(tmp_dir, "acc1", [_row(5)])
        upsert(tmp_dir, "acc1", [_row(5)])
        rows = read_pending(tmp_dir, "acc1")
        assert len(rows) == 1
        assert rows[0].priority == 1
        assert rows[0].force_include is True

    def test_upsert_refreshes_snapshot_on_repeat(self, tmp_dir):
        """Si el cliente vuelve a fallar con datos editados (dirección
        corregida, etc.), el snapshot del CSV se actualiza al más reciente."""
        upsert(tmp_dir, "acc1", [_row(5, name="Ana")])
        upsert(tmp_dir, "acc1", [_row(5, name="Ana Corregida")])
        rows = read_pending(tmp_dir, "acc1")
        assert rows[0].customer_name == "Ana Corregida"

    def test_accounts_are_isolated(self, tmp_dir):
        upsert(tmp_dir, "acc1", [_row(1)])
        upsert(tmp_dir, "acc2", [_row(2)])
        assert [r.cliente_id for r in read_pending(tmp_dir, "acc1")] == [1]
        assert [r.cliente_id for r in read_pending(tmp_dir, "acc2")] == [2]

    def test_read_pending_no_file_returns_empty(self, tmp_dir):
        assert read_pending(tmp_dir, "nunca-existio") == []


class TestRemove:
    def test_remove_deletes_only_given_ids(self, tmp_dir):
        """RN-034: al remover, solo desaparecen los ids pedidos, el resto persiste.

        spec: RN-034
        """
        upsert(tmp_dir, "acc1", [_row(1), _row(2)])
        remove(tmp_dir, "acc1", [1])
        rows = read_pending(tmp_dir, "acc1")
        assert [r.cliente_id for r in rows] == [2]

    def test_remove_on_missing_file_is_noop(self, tmp_dir):
        remove(tmp_dir, "nunca-existio", [1])  # no debe explotar
