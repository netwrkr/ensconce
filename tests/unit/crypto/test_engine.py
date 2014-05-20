import os
import binascii

from ensconce.crypto import engine
from ensconce import exc

from tests import BaseModelTest

class EngineTest(BaseModelTest):
    
    def test_encrypt_decrypt(self):
        """ Basic encryption/decryption tests. """
        
        
        #    012345678901234567890123456789012345678901234567890123456789
        #    1         2         3         4         5         6
        a = "The slow dog jumped over."
        b = "The slow dog jumped over the brown fox."
        c = "The slow dog jumped over the brown fox and the roosters too."
    
        a_c = engine.encrypt(a)
        self.assertIsInstance(a_c, str)
        
        self.assertEquals(a, engine.decrypt(a_c))
        
        b_c = engine.encrypt(b)
        self.assertEquals(b, engine.decrypt(b_c))
        
        c_c = engine.encrypt(c)
        self.assertEquals(c, engine.decrypt(c_c))
        
    def test_binary(self):
        """ Test encrypt/decrypt of non-ascii data. """
        data = os.urandom(100) # 100 bytes of binary data
        
        data_c = engine.encrypt(data)
        self.assertEquals(data, engine.decrypt(data_c))
    
    def test_empty(self):
        """ Test encrypt/decrypt behavior when using empty/None values. """
        self.assertNotEquals("", engine.encrypt(""), "Expected empty strings to actually be encryptable.")
        self.assertIs(None, engine.encrypt(None))
        
        self.assertEquals(None, engine.decrypt(""))
        self.assertIs(None, engine.decrypt(None))
        
    def test_decrypt_garbage(self):
        """ Test that exceptions are raised when decrypt input is garbage. """
        data = os.urandom(100) # 100 bytes of garbage
        with self.assertRaises(exc.CryptoAuthenticationFailed):
            engine.decrypt(data)
        
        # We'll also make it look more like the expected data format
        with self.assertRaises(exc.CryptoAuthenticationFailed):
            engine.decrypt(binascii.hexlify(data))
        
        # And finally we'll even add a pad string, but we still expect
        # an error like "Input strings must be a multiple of 16 in length."
        with self.assertRaises(exc.CryptoAuthenticationFailed):
            engine.decrypt(binascii.hexlify(("%02d" % 10) + data))