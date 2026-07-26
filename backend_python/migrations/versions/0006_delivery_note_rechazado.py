"""Nota de entrega + estado 'rechazado' (Etapa 4).

delivery_note: texto libre que deja el repartidor/operario al marcar un
estado (ej. "no había nadie, dejé con el vecino del 302" / "cliente rechazó
por precio") — hoy el único registro es el status en sí, sin contexto, lo que
obliga a preguntar por WhatsApp/llamada cada vez que hay una duda.

'rechazado': el cliente devuelve o no acepta el pedido en la puerta — distinto
de 'no_encontrado' (nadie atendió). Se agrega al CHECK existente y se trata
como no-terminal (reprogramable) igual que 'no_encontrado', ya que hay
ocasiones (rechazo por vuelto, por horario) donde reintentar tiene sentido.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-25
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS delivery_note TEXT;")
    op.execute("ALTER TABLE clientes DROP CONSTRAINT IF EXISTS clientes_delivery_status_check;")
    op.execute("""
        ALTER TABLE clientes ADD CONSTRAINT clientes_delivery_status_check
            CHECK (delivery_status IN ('pendiente', 'entregado', 'no_encontrado', 'reprogramado', 'rechazado'));
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP CONSTRAINT IF EXISTS clientes_delivery_status_check;")
    op.execute("""
        ALTER TABLE clientes ADD CONSTRAINT clientes_delivery_status_check
            CHECK (delivery_status IN ('pendiente', 'entregado', 'no_encontrado', 'reprogramado'));
    """)
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS delivery_note;")
