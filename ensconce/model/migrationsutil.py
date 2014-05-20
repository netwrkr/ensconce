"""
Various utility functions.
"""
from __future__ import absolute_import
import os.path
import string

from Crypto.Random import random

from alembic.migration import MigrationContext
from alembic.context import EnvironmentContext
from alembic.config import Config
from alembic.script import ScriptDirectory

from ensconce import exc
from ensconce.autolog import log
from ensconce.model import meta

def create_config():
    """
    Create the Alembic Config object based on the application configuration.
    
    :rtype: :class:`alembic.config.Config`
    """
    from ensconce.config import config # Needs to be included locally otherwise circular dep
    
    try:
        repository = config['alembic.script_location']
        if not os.path.isdir(repository):
            raise exc.ConfigurationError('The alembic.script_location path ' + repository + ' does not exist.')
        elif not os.path.isfile(os.path.join(repository, 'env.py')):
            raise exc.ConfigurationError('The alembic.script_location path ' + repository + ' does not look like a migrations directory. (no env.py file)')
    except KeyError:
        raise exc.ConfigurationError("The alembic.script_location config setting is not present, so no database migration will be performed.")
    
    alembic_cfg = Config()
    alembic_cfg.set_main_option('script_location', repository)
    alembic_cfg.set_main_option('sqlalchemy.url', config['sqlalchemy.url'])
    
    return alembic_cfg


def get_database_version():
    """
    Gets the current database revision (partial GUID).
    :rtype: str
    """
    context = MigrationContext.configure(meta.engine)
    return context.get_current_revision()


def get_head_version():
    """
    Gets the latest model revision available (partial GUID).
    :rtype: str
    """
    alembic_cfg = create_config()
    script = ScriptDirectory.from_config(alembic_cfg)
    return script.get_current_head()
    