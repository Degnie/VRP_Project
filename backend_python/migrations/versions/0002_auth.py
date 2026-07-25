"""Auth: accounts, users, instancias.account_id.

Multi-tenancy liviano: una cuenta = un negocio. instancias.account_id es
nullable a propósito — instancias creadas antes de esta migración (sin
dueño) siguen siendo válidas, solo quedan sin cuenta asociada hasta que se
re-guarden vía un usuario autenticado (Etapa 2).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(255) PRIMARY KEY,
            account_id VARCHAR(255) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL CHECK (role IN ('dueño', 'operario', 'repartidor')),
            full_name VARCHAR(255),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    op.execute("""
        ALTER TABLE instancias ADD COLUMN IF NOT EXISTS account_id VARCHAR(255) REFERENCES accounts(id);
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE instancias DROP COLUMN IF EXISTS account_id;")
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute("DROP TABLE IF EXISTS accounts;")
