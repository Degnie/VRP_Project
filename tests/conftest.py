"""
Pytest configuration and shared fixtures
"""

import os
import subprocess
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def _run_migrations():
    """
    Aplica las migraciones Alembic una sola vez por sesión de tests, antes de
    cualquier test que toque Postgres. PostgreSQLAdapter ya no ejecuta DDL
    propio (ver backend_python/persistence/postgres_adapter.py) — el schema
    ahora es responsabilidad exclusiva de Alembic.

    Se salta si no hay DATABASE_URL configurada, igual que los tests de
    persistencia (@pytest.mark.skipif) — evita fallar en un entorno sin
    Postgres disponible.
    """
    if not os.getenv("DATABASE_URL"):
        return
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
