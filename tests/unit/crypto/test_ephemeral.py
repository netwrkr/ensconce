import os
import hashlib

from ensconce.crypto import MasterKey, state, util as crypto_util
from ensconce import exc

from tests import BaseModelTest

class EphemeralStateTest(BaseModelTest):
    
    def setUp(self):
        super(EphemeralStateTest, self).setUp()
        # We need to reset the state 
        state.secret_key = None
        #crypto_util.clear_key_metadata()
    
    def _set_key(self, encryption_key, signing_key):
        """
        Sets a key on the ephemeral store; this method also takes care of
        setting up the key metadata (otherwise loading mismatched key will fail).
        """
        state.secret_key = None
        key = MasterKey(encryption_key=encryption_key, signing_key=signing_key)
        crypto_util.initialize_key_metadata(key=key, salt=os.urandom(8), force_overwrite=True)
        state.secret_key = key
        
    def tearDown(self):
        # Remove key_metadata rows so that they can be re-initialized.
        super(EphemeralStateTest, self).tearDown()
        crypto_util.initialize_key_metadata(key=self.SECRET_KEY, salt=os.urandom(8), force_overwrite=True)
        
    def test_initialized(self):
        """ Test ephemeral state initialization check. """
        self.assertFalse(state.initialized)
        self._set_key(hashlib.sha256('secret').digest(), hashlib.sha256('sign').digest())
        self.assertTrue(state.initialized)
        
    def test_access_uninitialized(self):
        """ Test accessing uninitialized secret_key """ 
        state.secret_key = None
        with self.assertRaises(exc.CryptoNotInitialized):
            state.secret_key
    
    def test_already_initialized(self):
        """ Test already-initialized ephemeral state key setting. """
        self._set_key(hashlib.sha256('secret').digest(), hashlib.sha256('sign').digest())
        
        ekey = hashlib.sha256('secret').digest()
        skey = hashlib.sha256('sign').digest()
        state.secret_key = MasterKey(ekey, skey)

    def test_set_different_key(self):
        """ Ensure that setting a new encryption key fails validation. """
        state.secret_key = None
        ekey = hashlib.sha256('new-key').digest()
        skey = hashlib.sha256('new-key').digest()
        with self.assertRaises(exc.IncorrectKey):
            state.secret_key = MasterKey(ekey, skey)
    
    def test_set_different_signing_key(self):
        """ Ensure that setting a new signing key fails validation. """
        self._set_key(hashlib.sha256('secret').digest(), hashlib.sha256('sign').digest())
        ekey = hashlib.sha256('secret').digest()
        skey = hashlib.sha256('new-key').digest()
        with self.assertRaises(exc.IncorrectKey):
            state.secret_key = MasterKey(ekey, skey)
            
    def test_set_incorrect_size(self):
        """ Test setting an incorrect sized key. """
        
        # We only support 32-char keys.
        with self.assertRaises(ValueError):
            state.secret_key = ""
            
        with self.assertRaises(ValueError):
            state.secret_key = hashlib.sha384('secret').digest()
            
        with self.assertRaises(ValueError):
            state.secret_key = hashlib.sha1().digest()
            
    def test_set_incorrect_type(self):
        """ Test setting with incorrect type. """
        with self.assertRaises(TypeError):
            state.secret_key = hashlib.sha1()