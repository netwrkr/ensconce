"""
Password hashing functions.
"""
from __future__ import absolute_import
import os
import re
import crypt # @UnresolvedImport
import hashlib
from base64 import encodestring as encode
from base64 import decodestring as decode

import bcrypt

from Crypto.Random import random

HASH_REGEXP = re.compile(r'^{([A-Z0-9]+)}(.*)$')

HASHTYPE_SSHA = 'SSHA'
HASHTYPE_CRYPT = 'CRYPT'
HASHTYPE_BCRYPT = 'BCRYPT'
        
def obscure(password, hashtype=HASHTYPE_BCRYPT):
    """
    Returns an obscured (hashed) version of a password.
    
    By default SSHA is used, which is SHA-1 hashed with random salt and 
    base64 encoded.  (This is a very LDAP-friendly password scheme.)
    
    :param password: The password to obscure.
    :type password: str
    
    :param hashtype: The hash type to use.  SSHA (default) and CRYPT supported.
    :type hashtype: str
    
    @return: An obscured version of the password.
    @rtype: str
    """
    if hashtype == HASHTYPE_SSHA:
        h = hashlib.sha1(password)
        salt = os.urandom(4)
        h.update(salt)
        return '{SSHA}' + encode(h.digest() + salt)[:-1]
    elif hashtype == HASHTYPE_CRYPT:
        salt = ''.join([chr(random.randint(64,126)) for x in range(8)])
        return '{CRYPT}' + crypt.crypt(password,'$1$'+salt)
    elif hashtype == HASHTYPE_BCRYPT:
        return '{BCRYPT}' + bcrypt.hashpw(password, bcrypt.gensalt()) # @UndefinedVariable
    else:
        raise ValueError("Unsupported hashtype: %s" % (hashtype,))

def is_obscured(password):
    return HASH_REGEXP.match(password)

def compare(obscured, password):
    """
    Compares an obscured password to a plaintext password.
    
    :param obscured: The obscured password, as returned by L{obscure}.
    :type obscured: str
    
    :param password: The plaintext password to compare.
    :type password: str
    
    @return: Whether the password matches.
    @rtype: bool
    """
    if obscured is None or password is None: # None != None, etc.
        return False
    
    m = HASH_REGEXP.match(str(obscured))
    if m is None:
        raise ValueError("Cannot parse type from hash: %s" % (obscured,))
    
    hashtype = m.group(1)
    hashval = m.group(2)
    
    if hashtype == HASHTYPE_SSHA:
        s = decode(hashval)
        digest = s[:20]
        salt = s[20:]
        h = hashlib.sha1(password)
        h.update(salt)
        return digest == h.digest()
    elif hashtype == HASHTYPE_CRYPT:
        return hashval == crypt.crypt(password, hashval)
    elif hashtype == HASHTYPE_BCRYPT:
        return hashval == bcrypt.hashpw(password, hashval) # @UndefinedVariable
    else:
        raise ValueError("Unsupported hash type: %s" % (hashtype,))

class PasswordDescriptor(object):
    """
    Stores a hashed version of a password in instance._password
        
    On get, returns a L{HashedPassword} instance, which implements
    equality and inequality operators for plaintext passwords.
    
    Passwords can be set as either obscured (beginning with '{SSHA}' or 
    other RFC 2307 supported hash type) or plaintext, which will be obscured 
    when set.
    """
    def __init__(self, hashtype='SSHA'):
        self.hashtype = hashtype
        
    def __get__(self, instance, owner):
        return HashedPassword(instance._password)

    def __set__(self, instance, value):
        if value is None or is_obscured(value):
            instance._password = value
        else:
            instance._password = obscure(value, self.hashtype)

class HashedPassword(object):
    """
    Wraps a password hashed and base64 encoded in LDAP style. Equality and
    inequality comparisons will check against a plaintext password.
        
    The string representation of this object is the obscured (hashed) password.
    
    Note that this object does not override the __hash__ method, so if you are
    expecting the equality check overrides to have an effect on uniqueness in 
    sets (or dict keys), you will be disappointed.
    """
    
    def __init__(self, obscured):
        self.obscured = obscured
    
    def __eq__(self, other):
        return compare(self.obscured, other)
        
    def __ne__(self, other):
        return not self == other
    
    def __str__(self):
        return self.obscured

