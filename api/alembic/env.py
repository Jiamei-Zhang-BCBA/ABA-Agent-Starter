import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment variable if set
db_url = os.environ.get("DATABASE_URL", "")
if db_url:
    # Convert async URLs to sync for Alembic
    db_url = db_url.replace("sqlite+aiosqlite", "sqlite").replace("postgresql+asyncpg", "postgresql")
    config.set_main_option("sqlalchemy.url", db_url)

# Import all models so Alembic can detect them
from app.database import Base
from app.models import *  # noqa: F401, F403

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
