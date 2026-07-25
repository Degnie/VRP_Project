"""Ciclo de vida de pedido (Etapa 4): estado de entrega + asignación repartidor↔vehículo.

Extiende `clientes` (ya es "el pedido" en el modelo actual) en vez de crear
una tabla nueva. `route_assignments` mapea qué repartidor lleva cada
vehicle_id de una instancia — vehicle_id no es una entidad persistida
propia, solo un índice dentro de la solución de esa instancia.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-25
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS external_tracking_code VARCHAR(255);")
    op.execute("""
        ALTER TABLE clientes ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(20) NOT NULL DEFAULT 'pendiente'
            CHECK (delivery_status IN ('pendiente', 'entregado', 'no_encontrado', 'reprogramado'));
    """)
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS delivery_updated_at TIMESTAMP;")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS delivery_updated_by VARCHAR(255) REFERENCES users(id);")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS rescheduled_to_instancia_id VARCHAR(255) REFERENCES instancias(id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS route_assignments (
            instancia_id VARCHAR(255) NOT NULL REFERENCES instancias(id) ON DELETE CASCADE,
            vehicle_id INT NOT NULL,
            repartidor_user_id VARCHAR(255) NOT NULL REFERENCES users(id),
            PRIMARY KEY (instancia_id, vehicle_id)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS route_assignments;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS rescheduled_to_instancia_id;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS delivery_updated_by;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS delivery_updated_at;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS delivery_status;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS external_tracking_code;")
