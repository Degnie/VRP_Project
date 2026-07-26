"""Borrar una instancia intermedia de una cadena de reprogramación no debe tirar 500.

Bug real (Ronda 43, confirmación — dueño): `clientes.rescheduled_to_instancia_id`
(agregada en 0005) referencia `instancias(id)` sin ninguna acción ON DELETE —
a diferencia de `route_assignments.instancia_id`, que sí tiene ON DELETE CASCADE.
Borrar una instancia B que es intermedia de una cadena A -> B -> C (B fue
creada al reprogramar A, y a su vez B fue reprogramada hacia C) fallaba con
un ForeignKeyViolation sin manejar en el endpoint, devuelto como 500 genérico:
los clientes de A que apuntan a B vía rescheduled_to_instancia_id bloqueaban
el DELETE FROM instancias. Sin corrupción de datos (Postgres hace rollback),
pero un flujo de dueño legítimo (limpiar instancias viejas de una cadena)
quedaba roto con un error sin explicación.

ON DELETE SET NULL en vez de CASCADE: borrar B no debe borrar en cascada los
clientes de A (que siguen existiendo, entregados o no, en su instancia
original) — solo se pierde la referencia "a dónde fueron reprogramados",
que de todos modos ya no apunta a ningún lado una vez que B no existe.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-26
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE clientes
            DROP CONSTRAINT IF EXISTS clientes_rescheduled_to_instancia_id_fkey;
    """)
    op.execute("""
        ALTER TABLE clientes
            ADD CONSTRAINT clientes_rescheduled_to_instancia_id_fkey
            FOREIGN KEY (rescheduled_to_instancia_id) REFERENCES instancias(id)
            ON DELETE SET NULL;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE clientes
            DROP CONSTRAINT IF EXISTS clientes_rescheduled_to_instancia_id_fkey;
    """)
    op.execute("""
        ALTER TABLE clientes
            ADD CONSTRAINT clientes_rescheduled_to_instancia_id_fkey
            FOREIGN KEY (rescheduled_to_instancia_id) REFERENCES instancias(id);
    """)
