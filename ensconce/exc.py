"""
Common exceptions for Ensconce application.
"""

class ConfigurationError(RuntimeError):
    pass 

class CryptoError(RuntimeError):
    pass

class CryptoAuthenticationFailed(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "The message fails to authenticate."
        super(CryptoAuthenticationFailed, self).__init__(msg)
        
class DatabaseAlreadyEncrypted(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "The database already has encrypted content."
        super(DatabaseAlreadyEncrypted, self).__init__(msg)
    
class CryptoNotInitialized(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Crypto engine has not been initialized."
        super(CryptoNotInitialized, self).__init__(msg)

class CryptoAlreadyInitialized(CryptoError):
    """
    For when we need to be working with un-initialized state.
    """
    def __init__(self, msg=None):
        if msg is None:
            msg = "Crypto engine has already been initialized."
        super(CryptoAlreadyInitialized, self).__init__(msg)
        
class IncorrectKey(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "The key did not match encrypted database contents."
        super(IncorrectKey, self).__init__(msg)

class MultipleKeyMetadata(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Multiple key metadata is not currently supported."
        super(MultipleKeyMetadata, self).__init__(msg)
        
class MissingKeyMetadata(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Database does not have any key metadata content."
        super(MissingKeyMetadata, self).__init__(msg)

class ExistingKeyMetadata(CryptoError):
    def __init__(self, msg=None):
        if msg is None:
            msg = "Database already has key metadata content."
        super(ExistingKeyMetadata, self).__init__(msg)


class AuthError(RuntimeError):
    """
    Generic top-level exception class for authentication and authorization errors.
    """

class InvalidCredentials(AuthError):
    """
    When username and/or password presented is invalid.
    """
    
class InsufficientPrivileges(AuthError):
    """
    When required privileges (group memberships, etc.) have not been met.
    """
    
class AuthorizationError(AuthError):
    """
    When user is not authorized to access a specific resource (e.g. missing ACL).
    """
 
class DatabaseError(RuntimeError):
    pass

class DatabaseVersionError(DatabaseError):
    """
    When version of database does not match available model version (migrations).
    """
    def __init__(self, msg=None):
        if msg is None:
            msg = "The database version does not match expectations."
        RuntimeError.__init__(self, msg)

class UnconfiguredModel(DatabaseError):
    """
    Exception to use when you need to have an initialized model (but don't).
    """
    def __init__(self, msg=None):
        if msg is None:
            msg = "The model layer has not yet been configured for the database."
        RuntimeError.__init__(self, msg)

class PermissionDenied(AuthorizationError):
    def __init__(self, userid, perm):
        super(PermissionDenied, self).__init__("User [{0}] does not have [{1}] permission.".format(userid, perm))
        
class NotLoggedIn(AuthorizationError):
    pass

class DataError(RuntimeError):
    pass

class DataIntegrityError(DataError):
    pass

class NoSuchEntity(DataError):
    def __init__(self, entity_class, key=None):
        msg = 'Unable to resolve {0} for specified key: {1!r}'.format(entity_class.__name__, key)
        super(NoSuchEntity, self).__init__(msg)
