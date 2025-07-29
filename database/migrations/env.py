from logging.config import fileConfig
import logging
from sqlalchemy import engine_from_config, pool, text

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, encoding='utf-8')

# add your model's MetaData object here
# for 'autogenerate' support
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))


from models import *
from models.model_base import GeneralStorageBase
target_metadata = GeneralStorageBase.metadata

# SQLAlchemy支持多个元数据对象自动合并

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

from sqlalchemy import inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alembic.env")


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
    print("配置的数据库 URL:", url) 
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
    engine = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
       

        
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=config.attributes.get("target_metadata"),
            version_table=f"alembic_version",  # 独立版本表
            compare_type=True,
            render_as_batch=True  # 兼容SQLite的DDL限制
            )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
