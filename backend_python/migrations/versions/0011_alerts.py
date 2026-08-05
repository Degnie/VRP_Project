"""Alertas del repartidor al dueño/operador (RN-024).

Notificación por polling: el repartidor crea una alerta ("No encuentro la
dirección") sobre un cliente de una instancia en curso; el dueño/operador la
consulta vía GET /alerts. Sin websockets — ver docs/delta-actual.md v1.5,
decisión aceptada.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-04
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id VARCHAR(255) PRIMARY KEY,
            account_id VARCHAR(255) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            instancia_id VARCHAR(255) NOT NULL,
            cliente_id INTEGER NOT NULL,
            repartidor_user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            motivo TEXT NOT NULL,
            resuelta BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_account_id ON alerts(account_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alerts;")
