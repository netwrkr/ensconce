from __future__ import absolute_import

from datetime import datetime
from dateutil.relativedelta import relativedelta

import pytz

from sqlalchemy.sql import and_

from ensconce import model, exc
from ensconce.model import meta
from ensconce.autolog import log
from ensconce.util import pwhash

def get(password_id, assert_exists=True):
    """
    Returns the operator object for specified ID.
    
    :param password_id: The ID for operator to lookup.
    :param assert_exists: Whether to raise :class:`exc.exception if entity does not exist (avoid NPE later).
    :rtype: :class:`model.Operator`
    """
    session = meta.Session()
    try:
        user = session.query(model.Operator).get(password_id)
    except:
        log.exception("Unable to retrieve user: {0}".format(password_id))
        raise
    
    if assert_exists and not user:
        raise exc.NoSuchEntity(model.Operator, password_id)
    
    return user
    
def get_by_username(username, assert_exists=True):
    """
    This function will attempt to match an operator by username.
    :param assert_exists: Whether to raise :class:`exc.exception if entity does not exist (avoid NPE later).
    """
    session = meta.Session()
    try:
        operator = session.query(model.Operator).filter_by(username=username).first()
    except:
        # The user ID didn't exist.
        log.exception("Unable to retrieve user for username: {0}".format(username))
        raise
    
    if assert_exists and not operator:
        raise exc.NoSuchEntity(model.Operator, username)
    
    return operator

def list(): # @ReservedAssignment
    """
    This function will return all of the operators in the system.
    """
    session = meta.Session()
    try:
        operators = session.query(model.Operator).order_by(model.Operator.username).all() # @UndefinedVariable
    except:
        log.exception("Error loading operator list.")
        raise
    else:
        return operators

def create(username, password=None, access_id=None, externally_managed=False):
    """
    This function will create an operator record in the database.
    
    :rtype: :class:`ensconce.model.Operator`
    """
    check = get_by_username(username, assert_exists=False)
    # First, check to see if the given username exists.
    if check:
        raise ValueError("User already exists: {0}".format(username))
        
    # Force the password to be null if it is empty (prevent logins w/ empty password)
    if password == "":
        password = None
        
    session = meta.Session()
    try:
        operator = model.Operator()
        operator.username = username
        if password is not None:
            operator.password = pwhash.obscure(password)
        operator.access_id = access_id
        operator.externally_managed = externally_managed
        session.add(operator)
        session.flush()
    except:
        log.exception("Error saving new operator_id.")
        raise
    
    return operator

def modify(operator_id, **kwargs):
    """
    This function will attempt to modify the operator with the passed
    in values.
    
    :keyword username: The username for this operator.
    :keyword password: The password for this operator.
    :keyword access_id: The associated access level id for this operator. 
    """
    session = meta.Session()
    update_attributes = kwargs # Just to make it clearer
    
    log.debug("Update attribs = %r" % update_attributes)
    
    # Force the password to be null if it is empty (prevent logins w/ empty password)
    if update_attributes.get('password') == "":
        update_attributes['password'] = None
    
    try:
        operator = get(operator_id)
        modified = model.set_entity_attributes(operator, update_attributes, hashed_attributes=['password'])
        session.flush()
    except:
        log.exception("Error modifying operator: {0}".format(operator_id))
        raise
    return (operator, modified)

def delete(password_id):
    """
    This function will attempt to delete a operatorid from the database.
    """
    session = meta.Session()
    try:
        operator = get(password_id)
        session.delete(operator)
    except:
        log.exception("Unable to delete operator: {0}".format(password_id))
        raise
    
    return operator