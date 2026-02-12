"""
Alembic migration environment.
Loads DATABASE_URL from .env and uses app models for autogenerate.
"""
import sys
from pathlib import Path

# Add project root so "backend" module is importable
# alembic/ is in backend/, project root is backend/..
_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from backend.app.core.config import settings
from backend.app.db.base import Base

# Import all models so they register with Base.metadata
import backend.app.models  # noqa: F401

config = context.config

# Override sqlalchemy.url with DATABASE_URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    from sqlalchemy import create_engine
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
