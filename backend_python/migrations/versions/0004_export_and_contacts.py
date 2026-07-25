"""Datos de contacto por cliente (Etapa 3): nombre, teléfono, dirección.

Antes vivían solo en memoria del frontend (ClientGroup.customerName/Phone/
address), nunca llegaban al backend — se perdían al recargar o al exportar
la hoja de ruta como PDF. Se agregan a `clientes` para persistirlos junto
con la instancia y poder incluirlos en el PDF de reparto.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-25
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255);")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50);")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS address VARCHAR(500);")


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS address;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS customer_phone;")
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS customer_name;")
