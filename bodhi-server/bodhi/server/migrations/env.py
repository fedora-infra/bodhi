# Copyright © 2013-2017 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Define the environment for Alembic migrations to run in."""

from logging.config import fileConfig
import logging

from alembic import context
from sqlalchemy import engine_from_config, pool, exc

from bodhi.server.config import config as bodhi_config
from bodhi.server.models import Base


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Use the options from the Bodhi config
config.set_main_option("sqlalchemy.url", bodhi_config["sqlalchemy.url"])

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.
_log = logging.getLogger('alembic.env')


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
    context.configure(url=url)

    with context.begin_transaction():
        # If the configuration indicates this script is for a Postgres-BDR database,
        # then we need to acquire the global DDL lock before migrating.
        postgres_bdr = config.get_main_option('offline_postgres_bdr')
        if postgres_bdr is not None and postgres_bdr.strip().lower() == 'true':
            _log.info('Emitting SQL to allow for global DDL locking with BDR')
            context.execute('SET LOCAL bdr.permit_ddl_locking = true')
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
        target_metadata=target_metadata)

    try:
        try:
            connection.execute('SHOW bdr.permit_ddl_locking')
            postgres_bdr = True
        except exc.ProgrammingError:
            # bdr.permit_ddl_locking is an unknown option, so this isn't a BDR database
            postgres_bdr = False
        with context.begin_transaction():
            if postgres_bdr:
                _log.info('Emitting SQL to allow for global DDL locking with BDR')
                connection.execute('SET LOCAL bdr.permit_ddl_locking = true')
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
