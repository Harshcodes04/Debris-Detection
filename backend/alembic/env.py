"""Alembic environment.

The database URL comes from the application's settings rather than alembic.ini,
so a migration always runs against the same database the app would use and there
is no second place to keep a connection string in step.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# alembic runs this file directly, so the package has to be importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings          # noqa: E402
from app.db import Base                  # noqa: E402
from app import models                   # noqa: E402,F401  (registers the tables)

# On SQLite the URL points at a file, and sqlite will not create the directory
# holding it. The app does this at startup; a migration on a fresh machine runs
# before that ever happens.
settings.ensure_directories()

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite cannot ALTER a column in place; batch mode rebuilds the
            # table instead, so the same migration runs on SQLite and Postgres.
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
