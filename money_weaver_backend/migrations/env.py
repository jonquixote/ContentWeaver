import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Make the backend package importable when alembic runs from a different cwd.
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL resolution must match fastapi_app/db.py:
# env var wins, fallback is the checked-in dev database.
_DEFAULT_DB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, 'src', 'database', 'app.db')
)
config.set_main_option(
    'sqlalchemy.url',
    os.getenv('DATABASE_URL', 'sqlite:///' + _DEFAULT_DB),
)

# Import every model module so autogenerate sees the full metadata.
from src.database import db  # noqa: E402
import src.models.user  # noqa: E402, F401
import src.models.project  # noqa: E402, F401
import src.models.task  # noqa: E402, F401
import src.models.media_asset  # noqa: E402, F401
import src.models.api_key  # noqa: E402, F401
import src.models.preset  # noqa: E402, F401
import src.models.template  # noqa: E402, F401
import src.models.voice  # noqa: E402, F401
import src.models.token_blocklist  # noqa: E402, F401

target_metadata = db.metadata

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
        render_as_batch=True,
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
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
