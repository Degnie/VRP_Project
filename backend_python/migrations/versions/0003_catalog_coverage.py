"""Catálogo de vehículos y zona de cobertura, ambos por cuenta.

Reemplazan lo que antes vivía solo en localStorage del navegador
(frontend/src/lib/vehicleCatalog.ts, coverageZone.ts) — persisten en
Postgres, asociados a account_id, compartidos entre todos los usuarios de
una misma cuenta.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-24
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_catalog (
            id VARCHAR(255) PRIMARY KEY,
            account_id VARCHAR(255) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            weight_capacity_kg FLOAT NOT NULL,
            volume_capacity_m3 FLOAT NOT NULL,
            tolerance_margin FLOAT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS coverage_zones (
            account_id VARCHAR(255) PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
            points JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS coverage_zones;")
    op.execute("DROP TABLE IF EXISTS vehicle_catalog;")
