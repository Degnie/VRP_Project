"""Un repartidor solo puede tener un vehicle_id por instancia.

Bug real: set_assignments (Etapa 4) no validaba que un repartidor_user_id
apareciera en más de un vehicle_id del mismo mapa de assignments —
get_assigned_vehicle_for_repartidor asume 1 vehículo por repartidor (su
query no tiene ORDER BY/LIMIT), así que un repartidor asignado a 2
vehículos veía una de sus dos rutas de forma no determinística, sin ningún
aviso. La Etapa de aplicación (Ronda 29) ya rechaza esto con 422, pero eso
no corrige datos que ya hayan quedado duplicados antes del fix, ni impide
que algún otro camino de escritura (futuro, o directo a la base) vuelva a
introducir el mismo estado inválido — el UNIQUE constraint lo hace
imposible independientemente del código de aplicación.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-25
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deduplica filas legacy antes de agregar el constraint — conserva una
    # sola fila por (instancia_id, repartidor_user_id), sin importar cuál
    # vehicle_id, ya que ambas rutas legacy ya eran indistinguibles vía la
    # query no determinística que este mismo bug produjo.
    op.execute("""
        DELETE FROM route_assignments a
        USING route_assignments b
        WHERE a.instancia_id = b.instancia_id
          AND a.repartidor_user_id = b.repartidor_user_id
          AND a.vehicle_id > b.vehicle_id;
    """)
    op.execute("""
        ALTER TABLE route_assignments
            ADD CONSTRAINT route_assignments_one_vehicle_per_repartidor
            UNIQUE (instancia_id, repartidor_user_id);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE route_assignments
            DROP CONSTRAINT IF EXISTS route_assignments_one_vehicle_per_repartidor;
    """)
