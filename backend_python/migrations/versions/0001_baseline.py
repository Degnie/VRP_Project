"""Baseline: schema tal cual existe hoy (instancias, flota_config, clientes).

Idempotente a propósito: usa CREATE TABLE IF NOT EXISTS porque bases ya
desplegadas antes de adoptar Alembic ya tienen estas tablas creadas por el
DDL manual de PostgreSQLAdapter (versión previa) — en esas bases, esta
migración se marca con `alembic stamp 0001` sin ejecutar el DDL de verdad.
En una base nueva, sí las crea.

Revision ID: 0001
Revises:
Create Date: 2026-07-24
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS instancias (
            id VARCHAR(255) PRIMARY KEY,
            nombre VARCHAR(255),
            num_clientes INT,
            depot_x FLOAT,
            depot_y FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS flota_config (
            instancia_id VARCHAR(255) PRIMARY KEY REFERENCES instancias(id) ON DELETE CASCADE,
            num_vehicles INT NOT NULL,
            capacity FLOAT NOT NULL,
            capacities FLOAT[]
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INT NOT NULL,
            instancia_id VARCHAR(255) NOT NULL REFERENCES instancias(id) ON DELETE CASCADE,
            demand FLOAT NOT NULL,
            x FLOAT NOT NULL,
            y FLOAT NOT NULL,
            PRIMARY KEY (id, instancia_id)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS clientes;")
    op.execute("DROP TABLE IF EXISTS flota_config;")
    op.execute("DROP TABLE IF EXISTS instancias;")
