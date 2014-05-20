"""
This is how ensconce used to do cryptography.

It's really bad, so this module only exists to provide an upgrade path.
"""
from __future__ import absolute_import

import binascii
import base64

from Crypto.Cipher import AES

from ensconce import exc
from ensconce.autolog import log

def create_engine(key):
    """
    Creates a new encryption engine.
    
    The encryption objects are not thread-safe and new ones should be created
    for every encryption/decryption operation.
    
    :param key: An optional explicit key may be passed if necessary; by default
                the key from the thread-safe ensconce.crypto.state object is used.
    :type key: str
    :returns: A new :class:`AES` object initialized with the symmetric key.
    :raise ensconce.exc.CryptoNotInitialized: If no key is specified and no key
                has yet been configured in global state.
    """
    
    if isinstance(key, unicode):
        key = key.encode('utf-8')
    assert isinstance(key, str)
    assert len(key) == 32
    return AES.new(key, AES.MODE_ECB)

def encrypt(cleartext, key):
    """
    Encrypts the specified data.
    
    :param data: The data to encrypt.  If unicode, will be converted to UTF-8.
    :type data: unicode or str
    
    :param key: The key to use.
    :type key: str
    
    :returns: A 2-byte prefix ("%02d" % num bytes of trailing padding) + ciphertext hexlified
    :rtype: str
    """
    if cleartext is None:
        return None
    elif isinstance(cleartext, unicode):
        cleartext = cleartext.encode('utf-8')
    
    assert isinstance(cleartext, str)
    
    if cleartext == "":
        return ""
        
    encodedtext = base64.b64encode(cleartext)
    
    # FIXME: We can use 32-byte block size ... right? (obviously requires re-encrypting everything) 
    BLOCK_SIZE = 16
    
    if len(encodedtext) % BLOCK_SIZE != 0:
        trail = BLOCK_SIZE - (len(encodedtext) % BLOCK_SIZE)
    else:
        trail = 0
        
    ciphertext = create_engine(key=key).encrypt(encodedtext + (trail * '0'))
    
    # We prefix the returned ciphertext with the number of bytes of padding.
    # XXX: This could be done more elegantly (e.g. interruptchar + padding), but would require 
    # re-encrypting everything.
    padding_prefix = "%02d" % trail
     
    return padding_prefix + binascii.hexlify(ciphertext)

def decrypt(ciphertext, key):
    """
    Decrypts the provided ciphertext (w/ padding prefix).
    
    :param ciphertext: A 2-byte prefix ("%02d" % num bytes of trailing padding) + ciphertext hexlified
    
    :param key: The key to use.
    :type key: str
    
    :return: The cleartext as a (UTF-8) string.
    :rtype: str or None (if the ciphertext is None)
    """
    if ciphertext is None:
        return None
    elif isinstance(ciphertext, unicode):
        ciphertext = ciphertext.encode('utf-8')
    
    assert isinstance(ciphertext, str)
    
    if ciphertext == "":
        return ""
    
    trail = int(ciphertext[:2]) # The first two bytes are ("%02d" % trail length)
    binary = binascii.unhexlify(ciphertext[2:])
    
    encoded = create_engine(key=key).decrypt(binary)
    
    if trail:
        encoded = encoded[:-trail]
        
    cleartext = base64.b64decode(encoded)
    
    return cleartext