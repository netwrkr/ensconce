"""
The encrypt and decrypt functions.

This code has evolved and current iteration is heavily inspired by
http://code.activestate.com/recipes/576980-authenticated-encryption-with-pycrypto/
"""
from __future__ import absolute_import

import hmac
import hashlib

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

from ensconce import exc
from ensconce.crypto import state, MasterKey
from ensconce.autolog import log

# All AES ciphers use a block size of 128 bits.
AES_BLOCK_SIZE = 16

# We are using method #2 of http://www.di-mgt.com.au/cryptopad.html since
# this lets us use huge padding lengths without worrying about communicating
# the length of the cleartext (i.e. we don't need to make a determination on
# max length of padding so it fits in X byte slot).
PADDING_DELIM_BYTE = 0x80
PADDING_BYTE = 0x00

SIGNATURE_SIZE = hashlib.sha256().digest_size

def encrypt(cleartext, key=None, chunksize=2048):
    """
    Encrypts the specified data.
    
    :param data: The data to encrypt.  If unicode, will be converted to UTF-8.
    :type data: unicode or str
    
    :param key: An optional explicit master key may be passed if necessary; by default
                the key from the thread-safe ensconce.crypto.state object is used.
    :type key: `ensconce.crypto.MasterKey`
    
    :param chunksize: The size (bytes) of the blocks to use for encryption.  This does
                      not have any bearing on how large the cipher blocks are, only how
                      large a the blocks of encrypted data should be (e.g. sufficiently
                      large sizes will prevent leaking information about cleartext
                      length).  
    :type chunksize: int
    
    :returns: The hex-encoded data (16-byte IV + ciphertext) + 32-byte HMAC signature 
    :rtype: str
    """
    if cleartext is None:
        return None
    elif isinstance(cleartext, unicode):
        cleartext = cleartext.encode('utf-8')
    
    assert isinstance(cleartext, str)
    
    if key is None:
        key = state.secret_key
    assert isinstance(key, MasterKey)
        
    cleartext += chr(PADDING_DELIM_BYTE) # Add the delimiter byte to the end. (This needs to be factored in now for padding calculations.)
     
    if len(cleartext) % chunksize != 0:
        padlen = chunksize - (len(cleartext) % chunksize)
    else:
        padlen = 0
    
    # We are going to use the AES block size here rather than the specified block size.
    iv_bytes = get_random_bytes(AES_BLOCK_SIZE)
    
    cypher = AES.new(key.encryption_key, AES.MODE_CBC, iv_bytes)
    
    ciphertext = cypher.encrypt(cleartext + (padlen * chr(PADDING_BYTE)))
    data = iv_bytes + ciphertext
    sig = hmac.new(key.signing_key, data, hashlib.sha256).digest()
    
    return data + sig

def decrypt(data, key=None):
    """
    Decrypts and authenticates the provided IV + payload + signature.
    
    :param data: The 16-byte IV + encrypted payload + 32-byte signature. 
    :type data: str
    
    :param key: An optional explicit master key may be passed if necessary; by default
                the key from the thread-safe ensconce.crypto.state object is used.
    :type key: ensconce.crypto.MasterKey
    
    :return: The cleartext as a (UTF-8) string.
    :rtype: str or None (if the ciphertext is None)
    """
    if data is None or data == "":
        return None
    elif isinstance(data, unicode):
        data = data.encode('utf-8')
    
    assert isinstance(data, str)

    if key is None:
        key = state.secret_key
    assert isinstance(key, MasterKey)

    sig = data[-SIGNATURE_SIZE:]
    data = data[:-SIGNATURE_SIZE]
    if hmac.new(key.signing_key, data, hashlib.sha256).digest() != sig:
        raise exc.CryptoAuthenticationFailed()
    
    # The first block is the IV
    iv_bytes = data[:AES_BLOCK_SIZE]
    data = data[AES_BLOCK_SIZE:]
    
    cypher = AES.new(key.encryption_key, AES.MODE_CBC, iv_bytes)
    cleartext = cypher.decrypt(data)
    
    # Remove all the trailing padding bytes.
    cleartext = cleartext.rstrip(chr(PADDING_BYTE))
    
    # Remove the delimiter byte
    cleartext = cleartext[:-1]
    
    return cleartext