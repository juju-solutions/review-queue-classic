from __future__ import with_statement

import os

from alembic import context
from ConfigParser import ConfigParser
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

from reviewq.models import Base


def load_ini(ini_file):
    """Load the settings for the bookie.ini file."""
    ini = ConfigParser()
    ini_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ini_file)
    ini.readfp(open(ini_path))
    here = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    ini.set('app:main', 'here', here)

    return ini


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

app_ini = config.get_main_option('app.ini',
                                 '%s.ini' % os.environ.get('ENV',
                                                           'development'))
app_config = load_ini(app_ini)
sa_url = app_config.get('app:main', 'sqlalchemy.url')
config.set_main_option('sqlalchemy.url', sa_url)

fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    engine = engine_from_config(
                config.get_section(config.config_ini_section),
                prefix='sqlalchemy.',
                poolclass=pool.NullPool)

    connection = engine.connect()
    context.configure(
                connection=connection,
                target_metadata=target_metadata
                )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

