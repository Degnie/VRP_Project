"""Optimistic locking en clientes para evitar lost-update entre solve y edición.

Bug real (Ronda 2, ciclo nuevo, operario): _solve_and_persist lee la instancia
completa (load_instance) en T0, corre el pipeline NN->SA->3-opt (que por
RNF-002/003 puede tardar segundos), y al terminar hace un upsert incondicional
del snapshot T0 vía save_instance. Si un PATCH /instances/{id}/clients/{id}
(update_client) de otro operario commiteaba una edición entre T0 y ese upsert
final, el solve la pisaba en silencio con los valores viejos — ambos requests
devolvían 200, sin ningún error.

Se agrega clientes.updated_at (actualizada en cada UPDATE de update_client) —
save_instance solo sobreescribe los campos editables (x, y, demand, contacto)
de un cliente si su updated_at en DB sigue coincidiendo con el snapshot que
load_instance trajo al iniciar el solve; si no coincide, esa fila se salta
(la edición concurrente gana), en vez de perderse.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-02
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE clientes
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE clientes DROP COLUMN IF EXISTS updated_at;")
