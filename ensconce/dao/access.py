from __future__ import absolute_import

from sqlalchemy.exc import IntegrityError

from ensconce import model, exc
from ensconce.autolog import log
from ensconce.cya import auditlog
from ensconce.dao import operators
from ensconce.model import meta

def get(access_id, assert_exists=True):
    """
    This function will return an Access class for a given access_id or None if it does not exist.
    :param password_id: The ID for operator to lookup.
    :param assert_exists: Whether to raise exception if entity does not exist (avoid NPE later).
    :rtype: :class:`model.Operator`
    """
    session = meta.Session()
    try:
        alevel = session.query(model.Access).get(access_id)
    except:
        log.exception("Unable to get access results for access_id: {0}".format(access_id))
        raise
    
    if assert_exists and not alevel:
        raise exc.NoSuchEntity(model.Resource, access_id)
    
    return alevel

def list(): # @ReservedAssignment
    """
    This function will return all of the access levels.
    """
    session = meta.Session()
    levels = session.query(model.Access).order_by(model.access_table.c.description).all() # @UndefinedVariable
    return levels

def delete(access_id):
    """
    This will delete an access level.
    """
    session = meta.Session()
    try:
        alevel = session.query(model.Access).get(access_id)
        session.delete(alevel)
        session.flush()
    except IntegrityError:
        log.exception("Error deleting ACLs for access_id: {0}".format(access_id))
        raise exc.DataIntegrityError("Cannot delete in-use access level.")
    except:
        log.exception("Error deleting ACLs for access_id: {0}".format(access_id))
        raise
    
    return alevel

def create(level_mask, description=None):
    """
    This function will create a new access level in the database.
    
    :raise ValueError: If unable to retrieve access level for ID.
    """
    session = meta.Session()
    existing = session.query(model.Access).filter_by(level=level_mask).first()
    
    if existing:
        raise ValueError("Access level_mask already exists: {0}".format(level_mask))

    try:
        alevel = model.Access()
        alevel.level = level_mask
        alevel.description = description
        session.add(alevel)
        session.flush()
    except:
        log.exception("Unable to create level_mask={0}".format(level_mask))
        raise

    return alevel

def modify(access_id, **kwargs):
    """
    This function will modify the description of an access level.
    :keyword level: The numeric access level mask.
    :keyword description: The  description for the new access level.
    :return: A tuple of access level object and modified rows.
    :raise ValueError: If unable to retrieve access level for ID.
    """
    alevel = get(access_id)
    if not alevel:
        raise ValueError("No matching access level found for ID: {0}".format(access_id))
    
    session = meta.Session()
    try:
        update_attributes = kwargs
        modified = model.set_entity_attributes(alevel, update_attributes)
        session.add(alevel)
        session.flush()
    except:
        log.exception("Unable to modify: {0}".format(access_id))
        raise
    
    return (alevel, modified)

def has_access(operator_id, level_mask=None):
    """
    This function will check to see whether specified operator_id has specified access level.
    
    :param operator_id: The user being checked.
    :param level_mask: The numeric level mask that is being checked.
    :type level_mask: int
    :return: Whether or not operator has access.
    :rtype: bool
    :raise ValueError: If operator_id cannot be resolved. 
    """
    user = operators.get(operator_id)
    return ((user.access.level & level_mask) != 0)
    
def verify_access(operator_id, level_mask=None):
    """
    This function will raise a PermissionDenied exception is user does not
    have access to specified level.
    
    :param operator_id: The user being checked.
    :param level_mask: The numeric level mask that is being checked.
    :type level_mask: int
    """
    if not has_access(operator_id=operator_id, level_mask=level_mask):
        raise exc.PermissionDenied(operator_id, level_mask)