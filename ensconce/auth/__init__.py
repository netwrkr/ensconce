"""
Authentication providers.
"""
#import importlib

from ensconce.autolog import log
from ensconce.config import config as global_config

def get_configured_providers(config=None):
    """
    Gets the authentication providers based on configuration.
    
    Multiple providers can be configured (failure will mean trying the next provider).
    
    :rtype: list
    """
    if config is None:
        config = global_config
    
    providers = []
    modnames = config['auth.provider']
    for modname in modnames:
        m = __import__("ensconce.auth." + modname, fromlist=[""])
        #m = importlib.import_module('ensconce.auth.{0}'.format(modname))
        providers.append(m.provider_from_config(config))
    return providers