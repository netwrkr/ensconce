"""
Various utility functions.
"""
from __future__ import absolute_import
import re
import string

from Crypto.Random import random

HASH_REGEXP = re.compile(r'^{([A-Z0-9]+)}(.*)$')

def generate_password(length=12, ascii_lower=True, ascii_upper=True, punctuation=True, 
                      digits=True, strip_ambiguous=False, strip_dangerous=True):
    """
    This function will return a password consisting of a mixture of lower
    and upper case letters, numbers, and non-alphanumberic characters
    in a ratio defined by the parameters.
    
    :param length: Length of generated password.
    :type length: int
    
    :param ascii_lower: Whether to include ASCII lowercase chars.
    :type ascii_lower: bool
    
    :param ascii_upper: Whether to include ASCII uppercase chars.
    :type ascii_upper: bool
    
    :param punctuation: Whether to include punctuation.
    :type punctuation: bool
    
    :param strip_ambiguous: Whether to remove easily-confused (LlOo0iI1) chars 
                            from the password.
    :type strip_ambiguous: bool
    :param strip_dangerous: Whethr to remove some of the more 'dangerous' punctuation 
                            (e.g. quotes) from the generated password.
    :type strip_dangerous: bool
    :returns: The generated password.
    :rtype: str
    """
    pool = []
    if ascii_lower:
        pool.extend(string.ascii_lowercase)
    if ascii_upper:
        pool.extend(string.ascii_uppercase)
    if punctuation:
        pool.extend(string.punctuation)
    if digits:
        pool.extend(string.digits)
    
    if strip_ambiguous:
        pool = set(pool) - set("LlOo0iI1")
        pool = list(pool) # Turn it back into a list since random.choice() needs indexing. 
    
    if strip_dangerous:
        pool = set(pool) - set(r'"\'`')
        pool = list(pool)
        
    if not pool:
        raise ValueError("No character classes enabled for password generation.")
    
    # Generate the total number of characters for the password
    return ''.join([random.choice(pool) for _i in range(length)])