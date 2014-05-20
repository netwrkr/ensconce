from __future__ import absolute_import

import functools

from ensconce import exc
from ensconce.dao import access
from ensconce.webapp.util import operator_info

# Access Levels
# 1     - User read                00000000 00000001 2^0
# 2     - User write               00000000 00000010 2^1
# 4     - Group read               00000000 00000100 2^2
# 8     - Group write              00000000 00001000 2^3
# 16    - Host read                00000000 00010000 2^4
# 32    - Host write               00000000 00100000 2^5
# 64    - Password read            00000000 01000000 2^6
# 128   - Password write           00000000 10000000 2^7
# 256   - Access read              00000001 00000000 2^8
# 512   - Access write             00000010 00000000 2^9
# 1024  - Audit log access         00000100 00000000 2^10
# 2048  - History reading          00001000 00000000 2^11
# Remainder are reserved for future use.

# Create a global access level dictionary that can be referenced in all of the
# classes and functions, so we can determine if the given access level is OK.

USER_R =        1 << 0
USER_W =        1 << 1
GROUP_R =       1 << 2
GROUP_W =       1 << 3
RESOURCE_R =    1 << 4
RESOURCE_W =    1 << 5
PASS_R =        1 << 6
PASS_W =        1 << 7
ACCESS_R =      1 << 8
ACCESS_W =      1 << 9
AUDIT =         1 << 10
HIST_R =        1 << 11

ACCESS_LEVEL_LABELS = ((USER_R, u'View Users'),
                       (USER_W, u'Modify Users'),
                       (GROUP_R, u'View Groups'), 
                       (GROUP_W, u'Modify Groups'),
                       (RESOURCE_R, u'View Resources'),
                       (RESOURCE_W, u'Modify Resources'),
                       (PASS_R, u'View Passwords'),
                       (PASS_W, u'Modify Passwords'),
                       (ACCESS_R, u'View Access Levels'),
                       (ACCESS_W, u'Modify Access Levels'),
                       (AUDIT, u'View Audit Log'),
                       (HIST_R, u'View History'),
                       )

ALL_ACCESS = reduce(lambda x,y: x|y, [val for (val,_lbl) in ACCESS_LEVEL_LABELS])

# XXX: This is kinda messy.  The check_acl method gets added to the individual methods,
# so we lose the clean_errors transformations if that method raises any errors.  
#
# This needs to be refactored a bit.

def require_access(perms):
    """
    A decorator that ensures that the currently logged-in user has the specified
    access level(s).
    :param perms: A single (int) perm or a list of (int) perms.
    """
    if isinstance(perms, (int, basestring)):
        perms = [perms]
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            # set name_override to func.__name__
            for perm in perms:
                access.verify_access(operator_info().user_id, perm)
            return f(*args, **kwargs)
        return wrapper
    return decorator

def has_access(perms):
    """
    Check whether current operator has the specified access perms.
    """
    if isinstance(perms, (int, basestring)):
        perms = [perms]
    return all([access.has_access(operator_info().user_id, perm) for perm in perms])