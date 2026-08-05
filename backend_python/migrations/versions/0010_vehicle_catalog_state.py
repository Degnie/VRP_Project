"""Estado operativo por tipo de vehículo (activo/suspendido).

RN-CAT-003: los vehículos suspendidos por mantenimiento no deben ser
asignables a nuevas instancias — hoy el catálogo no tiene ningún concepto
de disponibilidad, solo capacidades.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-04
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE vehicle_catalog ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'activo';")
    op.execute("""
        ALTER TABLE vehicle_catalog ADD CONSTRAINT vehicle_catalog_status_check
            CHECK (status IN ('activo', 'suspendido'));
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE vehicle_catalog DROP CONSTRAINT IF EXISTS vehicle_catalog_status_check;")
    op.execute("ALTER TABLE vehicle_catalog DROP COLUMN IF EXISTS status;")
