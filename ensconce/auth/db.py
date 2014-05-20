"""
Technically this is the default provider that just uses database to auth users.
"""

from ensconce import exc
from ensconce.autolog import log
from ensconce.dao import operators
from ensconce.util import pwhash

def provider_from_config(config):
    """
    Instantiates the provider class based on configuration.
    """
    return DbProvider()
    
class DbProvider(object):
    
    def authenticate(self, username, password):
        """
        This function will check the password passed in for the given
        userid against the database, and raise an exception if the authentication
        failse.
        
        :raise :class:`ensconce.exc.InvalidCredentials`: If username and/or password are invalid.
        """
        try:
            user = operators.get_by_username(username)
            if not pwhash.compare(user.password, password):
                raise exc.InvalidCredentials()
        except exc.NoSuchEntity:
            log.exception("No matching user.")
            raise exc.InvalidCredentials()
        
    def resolve_user(self, username):
        """
        Resolves the specified username to a database user, creating one if necessary.
        :rtype: :class:`ensconce.model.Operator` 
        """
        return operators.get_by_username(username)
    
    def __str__(self):
        return 'db-auth-provider'
    
    def __repr__(self):
        return '<{0}>'.format(self.__class__.__name__)