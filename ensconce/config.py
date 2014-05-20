"""
Configuration initialization utilities.
"""
from __future__ import absolute_import
import warnings
import os
import logging.config
from os.path import abspath, dirname, exists, join, realpath

import configobj
from validate import Validator

import pkg_resources

from ensconce.exc import ConfigurationError
from ensconce.model import init_model

MODULE_DIR = dirname(abspath(__file__))
ROOT_DIR = realpath(join(MODULE_DIR, ".."))

DEFAULT_CONFIG_FILES = ["/opt/ensconce/defaults.cfg",
                        "/etc/ensconce/settings.cfg",
                        join(ROOT_DIR, "development-defaults.ini"),
                        join(ROOT_DIR, "development.ini")]

DEFAULT_LOGGING_CONFIG_FILES = ["/etc/ensconce/logging.cfg",
                                join(ROOT_DIR, "logging.cfg")]

spec = configobj.ConfigObj(pkg_resources.resource_stream(__name__, "configspec.ini"), interpolation=False, list_values=False, encoding='utf-8') # @UndefinedVariable
config = configobj.ConfigObj(configspec=spec, encoding='utf-8')

def init_app(configfiles=None, drop_db=False, check_db_version=True):
    global config
    init_config(configfiles=configfiles)
    init_logging()
    init_model(config, drop=drop_db, check_version=check_db_version)
    
def init_config(configfiles=None):
    """
    Initialize the config object with values from the configuration files.
    
    :param configfiles: A list of config files (will default to DEFAULT_CONFIG_FILES module global)
    :type configfiles: list
    """
    global config
    
    if configfiles is None:
        configfiles = DEFAULT_CONFIG_FILES
        
    for fname in configfiles:
        if exists(fname):
            # This is a huge hack, but basically because I can't pass in a dict of "default"
            # values to ConfigObj constructure, I have to modify the actual "file" (well, the
            # list of lines from file) to prepend the value for 'root' else interpolation fails.
            # -1 for ConfigObj
            with open(fname) as fp:
                filelines =  [line for line in fp]        
            partial = configobj.ConfigObj(["root=%s\n" % ROOT_DIR] + filelines, encoding='utf-8')
            config.merge(partial)
    
    validation = config.validate(Validator(), preserve_errors=True)
    if validation != True:
        raise ConfigurationError("configuration validation error(s) (): {0!r}".format(configobj.flatten_errors(config, validation)))


def init_logging(configfiles=None):
    """
    Initialize the logging subsystem with specified config file(s).
    
    :param configfiles: A list of config files; the first file that exists will be passed to logging.config.fileConfig()
    """
    global config
    
    if configfiles is None:
        configfiles = DEFAULT_LOGGING_CONFIG_FILES
    
    import cherrypy # must do this before setting log levels
    import cherrypy._cplogging
    
    # TODO: Maybe make configurable. Currently we're just removing the [redundant] time.
    cherrypy._cplogging.LogManager.access_log_format = '%(h)s %(l)s %(u)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
    
    for fn in configfiles:
        if exists(fn):
            logging.config.fileConfig(fn)
            break
    else:
        # We couldn't find a config file that existed to initialize logging.
        logging.basicConfig(level=logging.INFO)
        warnings.warn("Unable to load config file from list: {0}".format(configfiles))