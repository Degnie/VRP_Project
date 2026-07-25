import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Permite `from backend_python.config import get_config` corriendo alembic
# desde la raíz del repo (mismo patrón que el resto del proyecto).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend_python.config import get_config  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Este proyecto no usa un ORM declarativo (los adapters en
# backend_python/persistence/ escriben SQL crudo vía psycopg2/psycopg) —
# las migraciones son SQL explícito (op.execute), no autogenerate desde
# modelos. target_metadata queda None a propósito.
target_metadata = None

# DATABASE_URL real del proyecto (psycopg2 o psycopg v3 según lo que esté
# instalado, mismo fallback que backend_python/persistence/postgres_adapter.py).
# SQLAlchemy necesita el dialect explícito en la URL: postgresql+psycopg2://
# o postgresql+psycopg:// — la URL de Config es un postgresql:// plano.
def _sqlalchemy_url() -> str:
    raw_url = get_config().DATABASE_URL
    try:
        import psycopg2  # noqa: F401
        dialect = "postgresql+psycopg2"
    except ImportError:
        dialect = "postgresql+psycopg"
    return raw_url.replace("postgresql://", f"{dialect}://", 1)


config.set_main_option("sqlalchemy.url", _sqlalchemy_url())

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
