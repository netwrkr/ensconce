"""
"""
import threading
from collections import namedtuple

from ensconce.exc import CryptoNotInitialized, IncorrectKey

MasterKey = namedtuple('MasterKey', ['encryption_key', 'signing_key'])

class CombinedMasterKey(MasterKey):
    def __new__(cls, combined_key):
        if isinstance(combined_key, unicode):
            combined_key = combined_key.encode('utf-8')
        if not isinstance(combined_key, str):
            raise TypeError("Combined key must be byte string; got {0}".format(type(combined_key)))
        if len(combined_key) != 64:
            raise ValueError("Combined keys must be 64-bytes.")
        return MasterKey.__new__(cls, encryption_key=combined_key[:32], signing_key=combined_key[32:])
    
class _EphemeralStore(object):
    """
    A class that is used to store sensitive key information that we need to 
    keep in memory.
    """
    _secret_key = None
    key_lock = None
    
    def __init__(self):
        self.key_lock = threading.RLock()
            
    # It's true that the locking here is probably overkill given implementation
    # details of cpython, but it serves as a [maybe-useful] reminder that this
    # app and all shared data exists in a multi-threaded context.
    
    @property
    def initialized(self):
        """ Whether the ephemeral store has been initialized. """
        with self.key_lock:
            return (self._secret_key is not None)
    
    @property
    def secret_key(self):
        """ Get the private key; will raise an exception if the key is not set. """
        with self.key_lock:
            if self._secret_key is None:
                raise CryptoNotInitialized("secret_key has not been initialized")
            return self._secret_key 
        
    @secret_key.setter
    def secret_key(self, value):
        """
        Sets the combined encryption/signing key to the specified value, raising exception
        if the key is not 64 bytes.  Internally the key is split in half; one half used for
        encryption and the other for signing.
        """
        # Need a runtime import since otherwise we have circular dep
        from ensconce.crypto import util
        
        with self.key_lock:
            if value is None:
                self._secret_key = None
            else:
                if not isinstance(value, MasterKey):
                    value = CombinedMasterKey(value)
                if not util.validate_key(value):
                    raise IncorrectKey()
                
                self._secret_key = value
                
    @property
    def encryption_key(self):
        """ Get just the encryption key from the combined master key. """
        return self.secret_key.encryption_key
        
    @property
    def signing_key(self):
        """ Get just the signing key from the combined master key. """
        return self.secret_key.signing_key
        
state = _EphemeralStore()
