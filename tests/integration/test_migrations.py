"""
Tests de migraciones Alembic: idempotencia y schema real.

El fixture de sesión `_run_migrations` en conftest.py ya corrió
`alembic upgrade head` antes de esta suite — estos tests verifican que el
resultado es correcto y que correr las migraciones dos veces seguidas no
falla ni bloquea (replica el bug real de locks encontrado en una fase
anterior, cuando el DDL vivía en PostgreSQLAdapter._init_schema()).
"""

import os
import subprocess
import sys

import pytest

POSTGRES_AVAILABLE = os.getenv("DATABASE_URL") is not None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _run_alembic(*args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        check=True,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="PostgreSQL not configured")
class TestMigrations:
    def test_upgrade_head_is_idempotent(self):
        """Correr `alembic upgrade head` dos veces seguidas no falla ni bloquea."""
        _run_alembic("upgrade", "head")
        _run_alembic("upgrade", "head")

    def test_baseline_tables_exist_with_expected_columns(self):
        """Tras la migración, las 3 tablas base existen con sus columnas."""
        from backend_python.persistence.postgres_adapter import PostgreSQLAdapter

        adapter = PostgreSQLAdapter()
        try:
            cursor = adapter.conn.cursor()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name IN "
                "('instancias', 'flota_config', 'clientes')"
            )
            tables = {row[0] for row in cursor.fetchall()}
            assert tables == {"instancias", "flota_config", "clientes"}

            cursor.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'flota_config'"
            )
            columns = {row[0] for row in cursor.fetchall()}
            assert "capacities" in columns
            cursor.close()
        finally:
            adapter.close()

    def test_current_revision_is_head(self):
        """`alembic current` reporta la revisión marcada como (head)."""
        result = _run_alembic("current")
        assert "(head)" in result.stdout
