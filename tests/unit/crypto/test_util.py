"""
Test the ensconce.crypto.utils package
"""
import os
import binascii
import hashlib

from ensconce.crypto import util, state, engine, MasterKey
from ensconce import exc, model
from ensconce.model import meta

from tests import BaseModelTest

class KeyValidationTest(BaseModelTest):
    """
    Test various functions related to key validation.
    """
    
    def setUp(self):
        super(KeyValidationTest, self).setUp()
            
    def tearDown(self):
        # Replace the key_metadata rows in cases test cases have changed this.
        super(KeyValidationTest, self).tearDown()
        util.initialize_key_metadata(key=self.SECRET_KEY, salt=os.urandom(8), force_overwrite=True)
           
    def test_derive_key(self):
        """ Test the key deriviation routines. """
        salt = os.urandom(8)
        key = util.derive_key("password", salt)
        self.assertEquals(32, len(key.encryption_key))
        self.assertEquals(32, len(key.signing_key))
        
        with self.assertRaises(ValueError):
            util.derive_key("password", salt[:4])
        
        key2 = util.derive_key("password", os.urandom(8))
        self.assertNotEqual(key, key2)
        
    def test_validate_key(self):
        """ Ensure successful key validation . """
        # Unset the global crypto engine state first.
        state.secret_key = None
        
        # Create a new key
        ekey = hashlib.sha256('encrypt').digest()
        skey = hashlib.sha256('sign').digest()
        key = MasterKey(encryption_key=ekey, signing_key=skey)
        
        # Now set new metadata
        util.initialize_key_metadata(key=key, salt=os.urandom(8), force_overwrite=True)
        
        # And then validate it.
        self.assertTrue(util.validate_key(key=key))
        
            
    def test_has_encrypted_data_basic(self):
        """ Ensure correct detection of encrypted data in db (basic). """
        # By default (with default data) this will be true
        self.assertTrue(util.has_encrypted_data())
        
        session = meta.Session()
        session.execute(model.passwords_table.delete())
        session.flush()
        
        # Should be true still ...
        self.assertTrue(util.has_encrypted_data())
        
        session.execute(model.resources_table.delete())
        session.flush()
        
        # But not anymore.
        self.assertFalse(util.has_encrypted_data())
        
    def test_has_encrypted_data_nulls(self):
        """ Ensure correct detection of encrypted data in db (null cols). """
        # By default (with default data) this will be true
        self.assertTrue(util.has_encrypted_data())
        
        session = meta.Session()
        session.execute(model.passwords_table.update().values(password=None))
        session.flush()
        
        self.assertTrue(util.has_encrypted_data())
        
        session.execute(model.resources_table.update().values(notes=None))
        session.flush()
        
        self.assertFalse(util.has_encrypted_data(), "With all password and notes field set to NULL, there should be no encrypted data in DB.")
        
    def test_initialize(self):
        """ Test initiazation of key metadata. """
        ekey = hashlib.sha256('encrypt').digest()
        skey = hashlib.sha256('sign').digest()
        new_key = MasterKey(encryption_key=ekey, signing_key=skey)
        with self.assertRaises(exc.CryptoAlreadyInitialized):
            util.initialize_key_metadata(key=new_key, salt=os.urandom(8))
            
        # Uninitailzie engine
        state.secret_key = None
         
        with self.assertRaises(exc.ExistingKeyMetadata):
            util.initialize_key_metadata(key=new_key, salt=os.urandom(8))
            
        util.initialize_key_metadata(key=new_key, salt=os.urandom(8), force_overwrite=True)
        self.assertTrue(util.validate_key(new_key))
        
    def test_replace_key(self):
        """ Test replacing the key (and re-encrypting the database). """
        
        self.assertTrue(util.has_encrypted_data())
        
        # Create a new key
        ekey = hashlib.sha256('new-encrypt').digest()
        skey = hashlib.sha256('new-sign').digest()
        new_key = MasterKey(encryption_key=ekey, signing_key=skey)
        
        with self.assertRaises(exc.DatabaseAlreadyEncrypted):
            util.replace_key(new_key)
        
        # Check existing passwords for an arbitrary user
        for (i,pw) in enumerate(self.data.resources['host1.example.com'].passwords.order_by('username')):
            self.assertEquals('password{0}'.format(i), pw.password_decrypted)
            
        util.replace_key(new_key, force=True)
        
        # The replace_key functions updates the global state, so this should work:
        for (i,pw) in enumerate(self.data.resources['host1.example.com'].passwords.order_by('username')):
            self.assertEquals('password{0}'.format(i), pw.password_decrypted)

        # But using the old key should, of course, now fail:
        for (i,pw) in enumerate(self.data.resources['host1.example.com'].passwords.order_by('username')):
            with self.assertRaises(exc.CryptoAuthenticationFailed):
                engine.decrypt(pw.password, key=self.SECRET_KEY)
            
        